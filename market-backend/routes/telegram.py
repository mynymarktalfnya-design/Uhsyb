"""Telegram reporting bot for the Uhsyb mini-market.

The module intentionally uses Telegram's HTTPS Bot API directly so it does not
require a long-running polling worker. Telegram posts updates to the webhook.
"""
from __future__ import annotations

import io
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests
from fastapi import APIRouter, HTTPException, Request

from database import C, db
from utils.time import day_range_utc, month_range_utc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/telegram", tags=["telegram"])
scheduled_router = APIRouter(prefix="/api/scheduled", tags=["scheduled"])

YEMEN_TZ = ZoneInfo("Asia/Aden")
TELEGRAM_API = "https://api.telegram.org/bot{}/{}"

BUTTONS = {
    "sales_today": "📈 مبيعات اليوم",
    "sales_month": "📈 مبيعات الشهر",
    "purchases_today": "💰 مشتريات اليوم",
    "purchases_month": "💰 مشتريات الشهر",
    "expenses_today": "💸 مصروفات اليوم",
    "expenses_month": "💸 مصروفات الشهر",
    "low_stock": "📦 المخزون المنخفض",
    "inventory": "📊 جرد المخزون",
    "help": "❓ مساعدة",
    "home": "🏠 القائمة الرئيسية",
}


def _token() -> str:
    return os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()


def _chat_id() -> str:
    # Support the canonical name and the legacy project setting name.
    return (
        os.environ.get("TELEGRAM_CHAT_ID", "").strip()
        or os.environ.get("TELEGRAMCHATID", "").strip()
    )


def _api(method: str, **kwargs: Any) -> dict:
    token = _token()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    response = requests.post(
        TELEGRAM_API.format(token, method),
        timeout=25,
        **kwargs,
    )
    response.raise_for_status()
    body = response.json()
    if not body.get("ok"):
        raise RuntimeError(body.get("description", "Telegram API error"))
    return body


def _keyboard() -> dict:
    return {
        "keyboard": [
            [BUTTONS["sales_today"], BUTTONS["sales_month"]],
            [BUTTONS["purchases_today"], BUTTONS["purchases_month"]],
            [BUTTONS["expenses_today"], BUTTONS["expenses_month"]],
            [BUTTONS["low_stock"], BUTTONS["inventory"]],
            [BUTTONS["help"], BUTTONS["home"]],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def send_message(text: str, chat_id: str | None = None, with_menu: bool = False) -> dict:
    target = str(chat_id or _chat_id())
    if not target:
        raise RuntimeError("TELEGRAM_CHAT_ID is not configured")
    payload: dict[str, Any] = {"chat_id": target, "text": text}
    if with_menu:
        payload["reply_markup"] = _keyboard()
    return _api("sendMessage", json=payload)


def send_document(content: bytes, filename: str, caption: str, chat_id: str) -> dict:
    result = _api(
        "sendDocument",
        data={"chat_id": chat_id, "caption": caption},
        files={"document": (filename, io.BytesIO(content), "application/pdf")},
    )
    logger.info("Telegram PDF sent successfully: %s", filename)
    return result


def _period(period: str) -> tuple[datetime, datetime, str]:
    now = datetime.now(YEMEN_TZ)
    if period == "month":
        start, end = month_range_utc(now.year, now.month)
        label = f"{now.year:04d}-{now.month:02d}"
    else:
        start, end = day_range_utc(now.date())
        label = now.strftime("%Y-%m-%d")
    return start, end, label


def _sum(rows: Any, field: str = "total") -> float:
    return round(sum(float(row.get(field, 0) or 0) for row in rows), 2)


def _sales_report(period: str) -> dict:
    start, end, label = _period(period)
    sales = list(db[C.sales].find({"created_at": {"$gte": start, "$lte": end}, "status": "completed", "deleted_at": None}))
    returns = list(db[C.sale_returns].find({"created_at": {"$gte": start, "$lte": end}, "status": "approved", "deleted_at": None}))
    gross = _sum(sales)
    returned = _sum(returns)
    by_method: dict[str, float] = {}
    for row in sales:
        method = str(row.get("payment_method") or "other")
        by_method[method] = by_method.get(method, 0.0) + float(row.get("total", 0) or 0)
    return {"label": label, "count": len(sales), "gross": gross, "returns": returned, "net": round(gross - returned, 2), "by_method": by_method}


def _purchase_report(period: str) -> dict:
    start, end, label = _period(period)
    rows = list(db[C.purchases].find({"created_at": {"$gte": start, "$lte": end}, "deleted_at": None}))
    return {"label": label, "count": len(rows), "total": _sum(rows)}


def _expense_report(period: str) -> dict:
    start, end, label = _period(period)
    rows = list(db[C.expenses].find({"created_at": {"$gte": start, "$lte": end}, "deleted_at": None}))
    return {"label": label, "count": len(rows), "total": _sum(rows)}


def _profit_report(period: str) -> dict:
    start, end, label = _period(period)
    sales = list(db[C.sales].find({"created_at": {"$gte": start, "$lte": end}, "status": "completed", "deleted_at": None}))
    sale_ids = [row.get("_id") for row in sales]
    items = list(db[C.sale_items].find({"sale_id": {"$in": sale_ids}})) if sale_ids else []
    product_ids = list({row.get("product_id") for row in items if row.get("product_id")})
    products = {row.get("_id"): row for row in db[C.products].find({"_id": {"$in": product_ids}})} if product_ids else {}
    cost = sum(float(products.get(item.get("product_id"), {}).get("cost_price", 0) or 0) * float(item.get("quantity", 0) or 0) for item in items)
    sales_data = _sales_report(period)
    expenses = _expense_report(period)["total"]
    return {"label": label, "net_sales": sales_data["net"], "cost": round(cost, 2), "expenses": expenses, "profit": round(sales_data["net"] - cost, 2), "net_profit": round(sales_data["net"] - cost - expenses, 2)}


def _inventory_rows(low_only: bool = False) -> list[dict]:
    products = list(db[C.products].find({"deleted_at": None}))
    rows = []
    for product in products:
        quantity = float(product.get("current_stock", product.get("stock", product.get("quantity", 0))) or 0)
        minimum = float(product.get("min_stock_level", product.get("min_stock", product.get("reorder_level", 0))) or 0)
        if low_only and quantity > minimum:
            continue
        rows.append({"name": str(product.get("name") or "-"), "quantity": quantity, "minimum": minimum})
    return sorted(rows, key=lambda row: row["quantity"])


def _money(value: float) -> str:
    return f"{value:,.2f}"


def _text_report(kind: str, period: str) -> str:
    if kind == "sales":
        data = _sales_report(period)
        methods = "، ".join(f"{key}: {_money(value)}" for key, value in data["by_method"].items()) or "لا توجد مبيعات"
        return (f"📈 تقرير مبيعات {data['label']}\n\nعدد العمليات: {data['count']}\n"
                f"إجمالي المبيعات: {_money(data['gross'])}\nالمرتجعات: {_money(data['returns'])}\n"
                f"صافي المبيعات: {_money(data['net'])}\nحسب الدفع: {methods}")
    if kind == "purchases":
        data = _purchase_report(period)
        return f"💰 تقرير مشتريات {data['label']}\n\nعدد الفواتير: {data['count']}\nإجمالي المشتريات: {_money(data['total'])}"
    if kind == "expenses":
        data = _expense_report(period)
        return f"💸 تقرير مصروفات {data['label']}\n\nعدد المصروفات: {data['count']}\nالإجمالي: {_money(data['total'])}"
    data = _profit_report(period)
    return (f"📊 ملخص الأرباح {data['label']}\n\nصافي المبيعات: {_money(data['net_sales'])}\n"
            f"تكلفة المنتجات: {_money(data['cost'])}\nالربح قبل المصروفات: {_money(data['profit'])}\n"
            f"المصروفات: {_money(data['expenses'])}\n✅ صافي الربح بعد المصروفات: {_money(data['net_profit'])}")


def _pdf(title: str, lines: list[str]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas
    font_path = os.environ.get("TELEGRAM_PDF_FONT", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    if Path(font_path).exists():
        pdfmetrics.registerFont(TTFont("UhsybFont", font_path))
        font = "UhsybFont"
    else:
        font = "Helvetica"
    stream = io.BytesIO()
    page = canvas.Canvas(stream, pagesize=A4)
    width, height = A4
    page.setFont(font, 16)
    page.drawString(48, height - 58, "Uhsyb Mini Market")
    page.setFont(font, 13)
    page.drawString(48, height - 84, title)
    page.setFont(font, 10)
    y = height - 120
    for line in lines:
        if y < 48:
            page.showPage()
            page.setFont(font, 10)
            y = height - 48
        page.drawString(48, y, str(line)[:115])
        y -= 18
    page.save()
    return stream.getvalue()


def _rtl(value: str) -> str:
    """Shape Arabic text for ReportLab's left-to-right drawing engine."""
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(str(value)))
    except Exception:
        return str(value)


def _inventory_pdf() -> bytes:
    """Create a structured Arabic inventory valuation table."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font_path = os.environ.get("TELEGRAM_PDF_FONT", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    font = "Helvetica"
    if Path(font_path).exists():
        try:
            pdfmetrics.registerFont(TTFont("UhsybFont", font_path))
            font = "UhsybFont"
        except Exception:
            pass

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("InventoryTitle", parent=styles["Title"], fontName=font, fontSize=16, leading=20, alignment=TA_RIGHT)
    cell_style = ParagraphStyle("InventoryCell", parent=styles["Normal"], fontName=font, fontSize=7.5, leading=9, alignment=TA_RIGHT)
    header_style = ParagraphStyle("InventoryHeader", parent=cell_style, fontSize=7, leading=8, alignment=TA_CENTER, textColor=colors.white)

    def cell(value, style=cell_style):
        return Paragraph(_rtl(str(value)), style)

    rows = list(db[C.products].find({"deleted_at": None}).sort("name", 1))
    table_rows = [[
        cell("كود المنتج", header_style), cell("اسم المنتج", header_style),
        cell("السعر الأصلي", header_style), cell("السعر مع العمولة", header_style),
        cell("الكمية", header_style), cell("قيمة المخزون بدون أرباح", header_style),
        cell("قيمة المخزون مع الأرباح", header_style), cell("الربح", header_style),
    ]]
    total_cost = total_sale = total_profit = total_qty = 0.0
    for product in rows:
        qty = float(product.get("current_stock", 0) or 0)
        original = float(product.get("cost_price", 0) or 0)
        with_commission = float(product.get("sale_price", 0) or 0)
        stock_cost = qty * original
        stock_sale = qty * with_commission
        profit = stock_sale - stock_cost
        total_qty += qty
        total_cost += stock_cost
        total_sale += stock_sale
        total_profit += profit
        table_rows.append([
            cell(product.get("sku") or "-"), cell(product.get("name") or "-"),
            cell(_money(original)), cell(_money(with_commission)), cell(f"{qty:g}"),
            cell(_money(stock_cost)), cell(_money(stock_sale)), cell(_money(profit)),
        ])
    table_rows.append([
        cell("الإجمالي", header_style), cell(f"عدد المنتجات: {len(rows)}", header_style),
        cell("-", header_style), cell("-", header_style), cell(f"{total_qty:g}", header_style),
        cell(_money(total_cost), header_style), cell(_money(total_sale), header_style), cell(_money(total_profit), header_style),
    ])

    stream = io.BytesIO()
    doc = SimpleDocTemplate(stream, pagesize=landscape(A4), rightMargin=10 * mm, leftMargin=10 * mm, topMargin=10 * mm, bottomMargin=10 * mm)
    table = Table(table_rows, repeatRows=1, colWidths=[20*mm, 48*mm, 25*mm, 27*mm, 20*mm, 38*mm, 38*mm, 25*mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17324d")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#d9edf7")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#9aaabd")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f4f7fa")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story = [Paragraph(_rtl("جرد المخزون وتقييم الأرباح"), title_style), Spacer(1, 5 * mm), table]
    doc.build(story)
    return stream.getvalue()


def _send_requested_report(chat_id: str, kind: str, period: str, as_pdf: bool = False):
    text = _text_report(kind, period)
    if not as_pdf:
        send_message(text, chat_id, with_menu=True)
        return
    lines = [line.replace("📈 ", "").replace("💰 ", "").replace("💸 ", "").replace("📊 ", "") for line in text.splitlines()]
    filename = f"uhsyb_{kind}_{period}_{datetime.now(timezone.utc):%Y%m%d_%H%M}.pdf"
    send_document(_pdf(text.splitlines()[0], lines), filename, "✅ تم إنشاء التقرير بصيغة PDF", chat_id)


def _handle_text(chat_id: str, text: str):
    normalized = text.strip()
    if normalized in ("/start", "/menu", BUTTONS["home"]):
        send_message("مرحبًا بك في بوت إدارة ميني ماركت الفنية 🏪\nاختر التقرير المطلوب من القائمة:", chat_id, with_menu=True)
    elif normalized in (BUTTONS["sales_today"], "/sales_today"):
        _send_requested_report(chat_id, "sales", "today", as_pdf=True)
    elif normalized in (BUTTONS["sales_month"], "/sales_month"):
        _send_requested_report(chat_id, "sales", "month", as_pdf=True)
    elif normalized in (BUTTONS["purchases_today"], "/purchases_today"):
        _send_requested_report(chat_id, "purchases", "today", as_pdf=True)
    elif normalized in (BUTTONS["purchases_month"], "/purchases_month"):
        _send_requested_report(chat_id, "purchases", "month", as_pdf=True)
    elif normalized in (BUTTONS["expenses_today"], "/expenses_today"):
        _send_requested_report(chat_id, "expenses", "today", as_pdf=True)
    elif normalized in (BUTTONS["expenses_month"], "/expenses_month"):
        _send_requested_report(chat_id, "expenses", "month", as_pdf=True)
    elif normalized in (BUTTONS["inventory"], "/inventory"):
        filename = f"uhsyb_inventory_{datetime.now(timezone.utc):%Y%m%d_%H%M}.pdf"
        send_document(_inventory_pdf(), filename, "📊 تقرير جرد المخزون التفصيلي", chat_id)
    elif normalized in (BUTTONS["low_stock"], "/low_stock"):
        rows = _inventory_rows(low_only=True)
        text = "📦 المخزون المنخفض\n\n" + ("\n".join(f"{row['name']}: {row['quantity']:g} (الحد الأدنى {row['minimum']:g})" for row in rows) or "لا توجد منتجات منخفضة المخزون")
        send_message(text, chat_id, with_menu=True)
    elif normalized in (BUTTONS["help"], "/help"):
        send_message("استخدم الأزرار لاختيار التقرير. التقارير المالية والمخزون التفصيلي تُرسل كملفات PDF.", chat_id, with_menu=True)
    else:
        send_message("لم أفهم الطلب. استخدم أزرار القائمة الرئيسية.", chat_id, with_menu=True)


def send_daily_report() -> dict:
    target = _chat_id()
    if not target:
        raise RuntimeError("TELEGRAM_CHAT_ID is not configured")
    send_message("🌙 التقرير اليومي الساعة 10 مساءً بتوقيت اليمن\n\n" + _text_report("profit", "today"), target, with_menu=True)
    return {"ok": True, "chat_id": target}


@router.post("/webhook")
async def webhook(request: Request):
    configured_secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()
    if configured_secret and request.headers.get("x-telegram-bot-api-secret-token") != configured_secret:
        raise HTTPException(status_code=403, detail="invalid telegram secret")
    update = await request.json()
    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat") or {}
    text = message.get("text")
    if chat.get("id") is not None and text:
        if _chat_id() and str(chat["id"]) != _chat_id():
            return {"ok": True, "ignored": "unauthorized_chat"}
        try:
            _handle_text(str(chat["id"]), str(text))
        except Exception:
            logger.exception("Telegram update failed")
    return {"ok": True}


def _daily_report_endpoint():
    return send_daily_report()


@router.post("/daily-report")
def daily_report():
    return _daily_report_endpoint()


@scheduled_router.post("/telegram_daily_report")
def scheduled_daily_report():
    return _daily_report_endpoint()


@router.get("/status")
def status():
    return {"configured": bool(_token() and _chat_id()), "bot_token_configured": bool(_token()), "chat_id_configured": bool(_chat_id())}
