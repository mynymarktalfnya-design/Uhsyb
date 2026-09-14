#!/usr/bin/env python3
"""Private Telegram reports bot for Mabna Market.

Required environment:
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, and the app database settings
Optional: REPORTS_TIMEZONE=Asia/Aden

The bot only serves the configured chat ID. It supports /menu, daily sales,
daily purchases, supplier balances, and a detailed inventory PDF.
"""
from __future__ import annotations

import io
import json
import os
import time
from datetime import datetime, time as dt_time, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "market-backend"))
from database import get_db

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = str(os.environ.get("TELEGRAM_CHAT_ID", "")).strip()
TZ = ZoneInfo(os.environ.get("REPORTS_TIMEZONE", "Asia/Aden"))
if not TOKEN or not CHAT_ID:
    raise SystemExit("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required")

db = get_db()


def api(method: str, payload: dict | None = None, files: dict | None = None):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    if files:
        boundary = b"----MabnaTelegramBoundary"
        body = bytearray()
        fields = {**(payload or {}), **files}
        for key, value in fields.items():
            body.extend(b"--" + boundary + b"\r\n")
            if isinstance(value, tuple):
                filename, data, mime = value
                body.extend(f'Content-Disposition: form-data; name="{key}"; filename="{filename}"\r\n'.encode())
                body.extend(f"Content-Type: {mime}\r\n\r\n".encode())
                body.extend(data)
            else:
                body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n{value}'.encode())
            body.extend(b"\r\n")
        body.extend(b"--" + boundary + b"--\r\n")
        request = Request(url, data=bytes(body), headers={"Content-Type": f"multipart/form-data; boundary={boundary.decode()}"}, method="POST")
    else:
        data = urlencode(payload or {}).encode()
        request = Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    with urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode())
        if not result.get("ok"):
            raise RuntimeError(result.get("description", "Telegram API error"))
        return result.get("result")


def send(text: str, keyboard: dict | None = None):
    payload = {"chat_id": CHAT_ID, "text": text}
    if keyboard:
        payload["reply_markup"] = json.dumps(keyboard, ensure_ascii=False)
    return api("sendMessage", payload)


def send_pdf(filename: str, content: bytes, caption: str):
    return api("sendDocument", {"chat_id": CHAT_ID, "caption": caption}, {"document": (filename, content, "application/pdf")})


def day_range():
    now = datetime.now(TZ)
    start = datetime.combine(now.date(), dt_time.min, TZ).astimezone(timezone.utc)
    end = start + timedelta(days=1)
    return start, end, now.date().isoformat()


def money(value):
    return f"{float(value or 0):,.2f}"


def menu():
    return {"inline_keyboard": [
        [{"text": "مبيعات اليوم", "callback_data": "sales_today"}, {"text": "مشتريات اليوم", "callback_data": "purchases_today"}],
        [{"text": "حسابات التجار", "callback_data": "suppliers"}, {"text": "جرد المخزون PDF", "callback_data": "inventory_pdf"}],
    ]}


def configure_commands():
    api("setMyCommands", {"commands": json.dumps([
        {"command": "inventory", "description": "جرد المخزون PDF"},
        {"command": "sales_today", "description": "مبيعات اليوم"},
        {"command": "purchases_today", "description": "مشتريات اليوم"},
        {"command": "suppliers", "description": "حسابات التجار"},
    ], ensure_ascii=False)})


def sales_today():
    start, end, day = day_range()
    sales = list(db["sales"].find({"created_at": {"$gte": start, "$lt": end}, "status": "completed", "deleted_at": None}))
    total = sum(float(s.get("total", 0) or 0) for s in sales)
    rows, cogs = [], 0.0
    for sale in sales:
        names, sale_cogs = [], 0.0
        for item in db["sale_items"].find({"sale_id": sale["_id"]}):
            product = db["products"].find_one({"_id": item.get("product_id")}, {"name": 1}) or {}
            name = product.get("name", "غير معروف")
            names.append(name)
            sale_cogs += float(item.get("unit_cost", 0) or 0) * float(item.get("quantity", 0) or 0)
        cogs += sale_cogs
        rows.append(f"• {', '.join(names[:3]) or '—'} — {money(sale.get('total'))} ر.ي")
    text = f"📊 مبيعات اليوم {day}\nعدد الفواتير: {len(sales)}\nالإجمالي: {money(total)} ر.ي\nالتكلفة: {money(cogs)} ر.ي\nالربح التقريبي: {money(total-cogs)} ر.ي\n\n" + ("\n".join(rows[:40]) or "لا توجد مبيعات اليوم")
    send(text, menu())


def purchases_today():
    start, end, day = day_range()
    purchases = list(db["purchases"].find({"created_at": {"$gte": start, "$lt": end}, "deleted_at": None}))
    total = sum(float(p.get("total", 0) or 0) for p in purchases)
    rows = []
    for purchase in purchases:
        supplier = db["suppliers"].find_one({"_id": purchase.get("supplier_id")}, {"name": 1}) or {}
        rows.append(f"• {supplier.get('name', 'غير معروف')} — {money(purchase.get('total'))} ر.ي")
    send(f"🧾 مشتريات اليوم {day}\nعدد الفواتير: {len(purchases)}\nالإجمالي: {money(total)} ر.ي\n\n" + ("\n".join(rows[:40]) or "لا توجد مشتريات اليوم"), menu())


def supplier_list():
    buttons = []
    for supplier in db["suppliers"].find({"deleted_at": None}, {"name": 1}).sort("name", 1).limit(40):
        buttons.append([{"text": supplier.get("name", "بدون اسم"), "callback_data": f"supplier:{supplier['_id']}"}])
    send("اختر التاجر لعرض كشف الحساب:", {"inline_keyboard": buttons or [[{"text": "لا يوجد تجار", "callback_data": "noop"}]]})


def supplier_report(supplier_id: str):
    supplier = db["suppliers"].find_one({"_id": supplier_id})
    if not supplier:
        send("التاجر غير موجود.", menu()); return
    entries = list(db["supplier_accounts"].find({"supplier_id": supplier_id}).sort("created_at", 1))
    balance = sum(float(e.get("debit", 0) or 0) - float(e.get("credit", 0) or 0) for e in entries)
    purchases = sum(float(e.get("debit", 0) or 0) for e in entries if e.get("type") == "purchase")
    paid = sum(float(e.get("credit", 0) or 0) for e in entries)
    send(f"👤 كشف حساب التاجر: {supplier.get('name', '—')}\nإجمالي المشتريات: {money(purchases)} ر.ي\nالمدفوع: {money(paid)} ر.ي\nالرصيد الحالي: {money(balance)} ر.ي", menu())


def inventory_pdf():
    products = list(db["products"].find({"deleted_at": None, "is_active": True}).sort("name", 1))
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=18, leftMargin=18, topMargin=18, bottomMargin=18)
    styles = getSampleStyleSheet(); styles.add(ParagraphStyle(name="Arabic", parent=styles["Normal"], alignment=TA_RIGHT, fontName="Helvetica", fontSize=8))
    data = [["المنتج", "الكمية", "تكلفة الوحدة", "سعر البيع", "قيمة التكلفة", "قيمة البيع", "الربح المتوقع"]]
    total_cost = total_sale = 0.0
    for product in products:
        qty = float(product.get("stock", product.get("quantity", 0)) or 0)
        cost = float(product.get("cost_price", product.get("purchase_price", 0)) or 0)
        sale = float(product.get("sale_price", product.get("selling_price", 0)) or 0)
        cv, sv = qty * cost, qty * sale; total_cost += cv; total_sale += sv
        data.append([str(product.get("name", "—")), money(qty), money(cost), money(sale), money(cv), money(sv), money(sv-cv)])
    data.append(["الإجمالي", "", "", "", money(total_cost), money(total_sale), money(total_sale-total_cost)])
    table = Table(data, repeatRows=1, colWidths=[190, 60, 80, 80, 90, 90, 90])
    table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#0f2948")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .3, colors.grey), ("ALIGN", (0,0), (-1,-1), "RIGHT"), ("FONTSIZE", (0,0), (-1,-1), 8), ("BACKGROUND", (0,-1), (-1,-1), colors.HexColor("#fef3c7"))]))
    doc.build([Paragraph("جرد المخزون — ميني ماركت الفنية", styles["Title"]), Spacer(1, 8), table])
    send_pdf("inventory_report.pdf", buffer.getvalue(), f"جرد المخزون: {len(products)} منتج | قيمة البيع {money(total_sale)} ر.ي | الربح المتوقع {money(total_sale-total_cost)} ر.ي")


def handle(update):
    message = update.get("message") or update.get("callback_query", {}).get("message") or {}
    chat_id = str(message.get("chat", {}).get("id", ""))
    if chat_id != CHAT_ID:
        return
    callback = update.get("callback_query")
    if callback:
        data = callback.get("data", "")
        api("answerCallbackQuery", {"callback_query_id": callback["id"]})
        if data == "sales_today": sales_today()
        elif data == "purchases_today": purchases_today()
        elif data == "suppliers": supplier_list()
        elif data == "inventory_pdf": inventory_pdf()
        elif data.startswith("supplier:"): supplier_report(data.split(":", 1)[1])
        return
    text = (message.get("text") or "").strip().lower()
    if text in {"/start", "/menu", "القائمة"}:
        send("تم تحديث القائمة وإزالة الخيارات القديمة.", {"remove_keyboard": True})
        send("اختر التقرير المطلوب:", menu())
    elif text in {"/sales", "/sales_today", "مبيعات اليوم"}: sales_today()
    elif text in {"/purchases", "/purchases_today", "مشتريات اليوم"}: purchases_today()
    elif text in {"/suppliers", "حسابات التجار"}: supplier_list()
    elif text in {"/inventory", "جرد المخزون"}: inventory_pdf()
    else: send("الأوامر المتاحة: /menu /sales_today /purchases_today /suppliers /inventory", menu())


def main():
    offset = 0
    configure_commands()
    while True:
        try:
            updates = api("getUpdates", {"timeout": 45, "offset": offset}) or []
            for update in updates:
                offset = update["update_id"] + 1
                handle(update)
        except Exception as exc:
            print(f"telegram bot error: {exc}", flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
