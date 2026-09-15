#!/usr/bin/env python3
"""Interactive Telegram reporting facade for Mini Market الفنية.

Telegram is a read-only presentation layer. It reuses the same database,
report helpers, account statement functions, and inventory PDF renderer used by
FastAPI; it does not create parallel accounting or identifiers.
"""
from __future__ import annotations

import io
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "market-backend"))
from database import get_db, C, DB_BACKEND
from inventory_audit_report import build_inventory_snapshot, render_inventory_pdf, _p, _rtl, FONT, FONT_BOLD
from routes.reports import daily_sales, monthly_sales, profits, _purchase_report_row
from routes.customer_accounts import customer_statement
from routes.supplier_accounts import supplier_statement
from utils.time import business_today, day_range_utc, month_range_utc

SETTINGS_FILE = Path(__file__).resolve().parent.parent / "market-backend" / "data" / "telegram_settings.json"
try:
    SAVED = json.loads(SETTINGS_FILE.read_text(encoding="utf-8")) if SETTINGS_FILE.exists() else {}
except Exception:
    SAVED = {}
TOKEN = str(SAVED.get("bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN", "")).strip()
CHAT_ID = str(SAVED.get("chat_id") or os.environ.get("TELEGRAM_CHAT_ID", "")).strip()
ALLOWED_CHAT_IDS = {x.strip() for x in os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", CHAT_ID).split(",") if x.strip()}
TZ = ZoneInfo(os.environ.get("REPORTS_TIMEZONE", "Asia/Aden"))
if SAVED.get("enabled") is False or not TOKEN or not CHAT_ID:
    raise SystemExit("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required")

db = get_db()
PAGE_SIZE = 8
PENDING_SEARCH: dict[str, str] = {}
CALLBACK_GUARD: dict[tuple[str, str], float] = {}
REPORT_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="telegram-report")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s telegram-reports %(message)s")
logger = logging.getLogger("telegram-reports")


def api(method: str, payload: dict | None = None, files: dict | None = None):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    if files:
        boundary = b"----MMFReportBoundary"
        body = bytearray()
        for key, value in {**(payload or {}), **files}.items():
            body.extend(b"--" + boundary + b"\r\n")
            if isinstance(value, tuple):
                filename, data, mime = value
                body.extend(f'Content-Disposition: form-data; name="{key}"; filename="{filename}"\r\n'.encode())
                body.extend(f"Content-Type: {mime}\r\n\r\n".encode()); body.extend(data)
            else:
                body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n{value}'.encode())
            body.extend(b"\r\n")
        body.extend(b"--" + boundary + b"--\r\n")
        req = Request(url, data=bytes(body), headers={"Content-Type": f"multipart/form-data; boundary={boundary.decode()}"}, method="POST")
    else:
        req = Request(url, data=urlencode(payload or {}).encode(), headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    with urlopen(req, timeout=45) as response:
        result = json.loads(response.read().decode())
    if not result.get("ok"):
        raise RuntimeError(result.get("description", "Telegram API error"))
    return result.get("result")


def send(text: str, keyboard: dict | None = None, chat_id: str = CHAT_ID):
    payload = {"chat_id": chat_id, "text": text}
    if keyboard: payload["reply_markup"] = json.dumps(keyboard, ensure_ascii=False)
    return api("sendMessage", payload)


def send_pdf(filename: str, content: bytes, caption: str, chat_id: str = CHAT_ID):
    return api("sendDocument", {"chat_id": chat_id, "caption": caption}, {"document": (filename, content, "application/pdf")})


def money(value):
    return f"{float(value or 0):,.2f} ر.ي"


def day_range():
    today = business_today()
    start, end = day_range_utc(today)
    return start, end, today


def period_range(kind):
    today = business_today()
    if kind == "day": return day_range_utc(today)
    return month_range_utc(today.year, today.month)


def main_menu():
    return {"inline_keyboard": [
        [{"text": "📊 المبيعات", "callback_data": "menu:sales"}, {"text": "🛒 المشتريات", "callback_data": "menu:purchases"}],
        [{"text": "💰 الأرباح", "callback_data": "menu:profits"}, {"text": "👥 كشف حساب العملاء", "callback_data": "menu:customers"}],
        [{"text": "🏪 كشف حساب التجار", "callback_data": "menu:suppliers"}, {"text": "📦 جرد المخزون", "callback_data": "report:inventory"}],
        [{"text": "💸 المصروفات", "callback_data": "menu:expenses"}, {"text": "🔄 تحديث البيانات", "callback_data": "menu:home"}],
    ]}


def back_menu(): return {"inline_keyboard": [[{"text": "⬅️ رجوع", "callback_data": "menu:home"}]]}

def period_menu(prefix):
    return {"inline_keyboard": [[{"text": "🗓 اليوم", "callback_data": f"report:{prefix}:day"}, {"text": "📅 الشهر", "callback_data": f"report:{prefix}:month"}], [{"text": "⬅️ رجوع", "callback_data": "menu:home"}]]}


def list_menu(kind, page=0, query=""):
    collection = C.suppliers if kind == "supplier" else C.customers
    name_field = "name" if kind == "supplier" else "full_name"
    filt = {"deleted_at": None}
    if query:
        rx = {"$regex": query, "$options": "i"}
        filt["$or"] = [{name_field: rx}, {"phone": rx}, {"code": rx}]
    total = db[collection].count_documents(filt)
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    rows = list(db[collection].find(filt).sort(name_field, 1).skip(page * PAGE_SIZE).limit(PAGE_SIZE))
    buttons = []
    for row in rows[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]:
        label = str(row.get(name_field) or "بدون اسم")[:45]
        buttons.append([{"text": label, "callback_data": f"select:{kind}:{row['_id']}"}])
    nav = []
    if page > 0: nav.append({"text": "السابق", "callback_data": f"list:{kind}:{page-1}"})
    if page + 1 < pages: nav.append({"text": "التالي", "callback_data": f"list:{kind}:{page+1}"})
    if nav: buttons.append(nav)
    buttons.append([{ "text": "🔍 بحث", "callback_data": f"search:{kind}" }, {"text": "⬅️ رجوع", "callback_data": "menu:home"}])
    title = "التجار" if kind == "supplier" else "العملاء"
    return f"اختر {title} — صفحة {page+1}/{pages}", {"inline_keyboard": buttons}


def account_period_menu(kind, entity_id):
    return {"inline_keyboard": [
        [{"text": "كشف حساب اليوم", "callback_data": f"statement:{kind}:{entity_id}:day"}],
        [{"text": "كشف حساب الشهر", "callback_data": f"statement:{kind}:{entity_id}:month"}],
        [{"text": "كشف حساب كامل", "callback_data": f"statement:{kind}:{entity_id}:all"}],
        [{"text": "⬅️ رجوع", "callback_data": f"menu:{'suppliers' if kind == 'supplier' else 'customers'}"}],
    ]}


def inventory_pdf(chat_id=CHAT_ID):
    now = datetime.now(TZ)
    snapshot = build_inventory_snapshot(db, audit_no=f"AUD-{now.strftime('%Y%m%d-%H%M%S')}", actor_name="Telegram", branch="ميني ماركت الفنية", created_at=now)
    return send_pdf(f"جرد المخزون - ميني ماركت الفنية - {now:%Y-%m-%d}.pdf", render_inventory_pdf(snapshot), "كشف جرد المخزون الحالي", chat_id)


def sales_report(kind, chat_id=CHAT_ID):
    start, end, today = period_range(kind)
    if kind == "day":
        report = daily_sales(date=today.isoformat(), db=db, _u=None)
        title = f"📊 المبيعات اليومية — {today.isoformat()}"
    else:
        report = monthly_sales(year=today.year, month=today.month, db=db, _u=None)
        title = f"📊 المبيعات الشهرية — {today:%Y-%m}"
    credit = 0.0
    for sale in db[C.sales].find({"created_at": {"$gte": start, "$lt": end}, "status": "completed", "deleted_at": None, "payment_method": "credit"}, {"total": 1}): credit += float(sale.get("total", 0) or 0)
    send(f"{title}\n\nإجمالي المبيعات: {money(report['total_sales'])}\nإجمالي المرتجعات: {money(report['total_returns'])}\nإجمالي مبيعات الأجل: {money(credit)}\nصافي المبيعات بعد خصم المرتجعات: {money(report['net_sales'])}\nعدد الفواتير: {report['transactions_count']}\nعدد المرتجعات: {report['returns_count']}", back_menu(), chat_id)


def purchase_rows(kind):
    start, end = period_range(kind)
    rows = list(db[C.purchases].find({"created_at": {"$gte": start, "$lt": end}, "deleted_at": None}).sort("created_at", -1))
    return [_purchase_report_row(db, row) for row in rows]


def purchases_report(kind, chat_id=CHAT_ID):
    rows = purchase_rows(kind)
    title = "🛒 مشتريات اليوم" if kind == "day" else "🛒 المشتريات الشهرية"
    if kind == "month" and len(rows) > 4:
        return send_pdf(f"مشتريات-{business_today():%Y-%m}.pdf", build_purchase_pdf(rows, title), title, chat_id)
    chunks = [title]
    for invoice in rows:
        chunks.append(f"\nالتاجر: {invoice['supplier_name']}\nالفاتورة: {invoice['ref_no']}\nالتاريخ: {str(invoice['date'])[:19]}")
        for i, item in enumerate(invoice["items"], 1):
            chunks.append(f"{i}. {item['product_name']} — الكمية: {item['quantity']:,.2f} — سعر الشراء: {money(item['unit_cost'])} — الإجمالي: {money(item['total'])}")
        chunks.append(f"إجمالي الفاتورة: {money(invoice['total'])}")
    chunks.append(f"\nإجمالي المشتريات: {money(sum(x['total'] for x in rows))}\nعدد الفواتير: {len(rows)}")
    send("\n".join(chunks)[:3900], back_menu(), chat_id)


def expense_rows(kind):
    start, end = period_range(kind)
    dates = {"$gte": start.strftime("%Y-%m-%d"), "$lt": end.strftime("%Y-%m-%d")}
    rows = list(db[C.expenses].find({"expense_date": dates, "deleted_at": None}).sort("expense_date", -1))
    out = []
    for row in rows:
        cat = db[C.expense_categories].find_one({"_id": row.get("category_id")}) or {}
        out.append({**row, "category_name": cat.get("name") or "غير مصنف"})
    return out


def expenses_report(kind, chat_id=CHAT_ID):
    rows = expense_rows(kind)
    title = "💸 مصروفات اليوم" if kind == "day" else "💸 مصروفات الشهر"
    text = [title]
    for row in rows: text.append(f"\nالتاريخ: {row.get('expense_date') or '—'}\nالنوع: {row['category_name']}\nالوصف: {row.get('description') or '—'}\nالمبلغ: {money(row.get('amount'))}")
    text.append(f"\nإجمالي المصروفات: {money(sum(float(x.get('amount', 0) or 0) for x in rows))}")
    if len("".join(text)) > 3900: return send_pdf(f"مصروفات-{business_today():%Y-%m}.pdf", build_expense_pdf(rows, title), title, chat_id)
    send("".join(text), back_menu(), chat_id)


def profit_report(kind, chat_id=CHAT_ID):
    start, end = period_range(kind)
    report = profits(date_from=start.strftime("%Y-%m-%d"), date_to=(end - timedelta(days=1)).strftime("%Y-%m-%d"), db=db, _u=None)
    expenses = sum(float(x.get("amount", 0) or 0) for x in expense_rows(kind))
    gross = float(report["profit"])
    text = (f"💰 الأرباح {'اليومية' if kind == 'day' else 'الشهرية'}\n\n"
            f"إجمالي المبيعات: {money(report['revenue'])}\nإجمالي المرتجعات: {money(report['total_returns'])}\nصافي المبيعات: {money(report['net_revenue'])}\n"
            f"تكلفة المنتجات المباعة: {money(report['cost'])}\nإجمالي الربح قبل المصروفات: {money(gross)}\nإجمالي المصروفات: {money(expenses)}\nصافي الربح بعد المصروفات: {money(gross - expenses)}")
    if kind == "month" and report.get("items_count", 0) > 20: return send_pdf(f"أرباح-{business_today():%Y-%m}.pdf", build_profit_pdf(report, expenses), "تقرير الأرباح التفصيلي", chat_id)
    send(text, back_menu(), chat_id)


def statement(kind, entity_id, period, chat_id=CHAT_ID):
    entity = db[C.suppliers if kind == "supplier" else C.customers].find_one({"_id": entity_id, "deleted_at": None})
    if not entity: return send("السجل غير موجود.", back_menu(), chat_id)
    today = business_today(); start, end = period_range(period) if period != "all" else (None, None)
    if kind == "supplier":
        data = supplier_statement(entity_id, db=db, _u=None)
        name = entity.get("name", "—")
        entries = data.get("entries", [])
        if start: entries = [x for x in entries if x.get("date") and start <= x["date"] < end]
        summary = data.get("summary", {})
    else:
        data = customer_statement(entity_id, date_from=start.strftime("%Y-%m-%d") if start else None, date_to=(end - timedelta(days=1)).strftime("%Y-%m-%d") if end else None, db=db, _u=None)
        name = entity.get("full_name", "—"); entries = data.get("entries", []); summary = {"balance": data.get("closing_balance", 0)}
    title = f"كشف حساب {'التاجر' if kind == 'supplier' else 'العميل'}: {name}"
    if len(entries) > 12: return send_pdf(f"كشف-{entity_id}.pdf", build_statement_pdf(title, entries, summary), title, chat_id)
    lines = [title, f"الفترة: {'كامل' if period == 'all' else ('اليوم' if period == 'day' else 'الشهر')}\n"]
    for entry in entries:
        lines.append(f"\n{str(entry.get('date'))[:10]} — {entry.get('op_no', '—')} — {entry.get('description', '—')} — مدين: {money(entry.get('debit'))} — دائن: {money(entry.get('credit'))} — الرصيد: {money(entry.get('balance'))}")
    lines.append(f"\nالرصيد: {money(summary.get('balance', data.get('closing_balance', 0)))}")
    send("".join(lines)[:3900], back_menu(), chat_id)


def build_pdf(title, headers, rows, filename):
    out = io.BytesIO(); doc = SimpleDocTemplate(out, pagesize=A4, rightMargin=10*mm, leftMargin=10*mm, topMargin=12*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet(); normal = ParagraphStyle("R", parent=styles["Normal"], fontName=FONT, fontSize=7, leading=9, alignment=TA_RIGHT); bold = ParagraphStyle("B", parent=normal, fontName=FONT_BOLD, fontSize=11, leading=14)
    table_data = [[_p(h, bold) for h in headers]] + [[_p(v, normal) for v in row] for row in rows]
    table = Table(table_data, repeatRows=1, splitByRow=1)
    table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#0f2948")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .3, colors.grey), ("ALIGN", (0,0), (-1,-1), "RIGHT"), ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")])]))
    doc.build([_p("ميني ماركت الفنية", bold), _p(title, bold), Spacer(1, 6), table])
    return out.getvalue()


def build_purchase_pdf(rows, title):
    data = [[str(x["date"])[:10], x["ref_no"], x["supplier_name"], item["product_name"], f"{item['quantity']:,.2f}", money(item["unit_cost"]), money(item["total"])] for x in rows for item in x["items"]]
    return build_pdf(title, ["التاريخ", "الفاتورة", "التاجر", "المنتج", "الكمية", "سعر الشراء", "إجمالي المنتج"], data, "purchases.pdf")

def build_expense_pdf(rows, title):
    return build_pdf(title, [["التاريخ", "نوع المصروف", "الوصف", "المبلغ"]][0], [[x.get("expense_date"), x["category_name"], x.get("description") or "—", money(x.get("amount"))] for x in rows], "expenses.pdf")

def build_statement_pdf(title, entries, summary):
    data = [[str(x.get("date"))[:10], x.get("op_no"), x.get("description"), money(x.get("debit")), money(x.get("credit")), money(x.get("balance"))] for x in entries]
    return build_pdf(title, ["التاريخ", "المرجع", "البيان", "مدين", "دائن", "الرصيد"], data, "statement.pdf")

def build_profit_pdf(report, expenses):
    rows = [["المبيعات", money(report["revenue"])], ["المرتجعات", money(report["total_returns"])], ["صافي المبيعات", money(report["net_revenue"])], ["تكلفة المنتجات المباعة", money(report["cost"])], ["الربح قبل المصروفات", money(report["profit"])], ["المصروفات", money(expenses)], ["صافي الربح", money(report["profit"] - expenses)]]
    return build_pdf("تقرير الأرباح التفصيلي", ["البند", "القيمة"], rows, "profits.pdf")


def handle(update):
    message = update.get("message") or update.get("callback_query", {}).get("message") or {}
    chat_id = str(message.get("chat", {}).get("id", ""))
    if chat_id not in ALLOWED_CHAT_IDS: return
    callback = update.get("callback_query")
    if callback:
        data = callback.get("data", ""); api("answerCallbackQuery", {"callback_query_id": callback["id"]})
        now = time.monotonic(); guard_key = (chat_id, data)
        if now - CALLBACK_GUARD.get(guard_key, 0) < 0.75:
            return
        CALLBACK_GUARD[guard_key] = now
        REPORT_EXECUTOR.submit(_run_callback, data, chat_id)
        return
    text = (message.get("text") or "").strip()
    if PENDING_SEARCH.get(chat_id):
        kind = PENDING_SEARCH.pop(chat_id); title, keyboard = list_menu(kind, 0, text); send(title, keyboard, chat_id); return
    if text.lower() in {"/start", "/menu", "menu", "القائمة", "القائمة الرئيسية"}:
        send("اختر التقرير المطلوب من النظام:", main_menu(), chat_id)
    elif text.lower() in {"/inventory", "جرد المخزون"}: inventory_pdf(chat_id)
    else: send("استخدم القائمة التفاعلية لاختيار التقرير.", main_menu(), chat_id)


def handle_callback(data, chat_id):
    parts = data.split(":")
    if data == "menu:home": send("اختر التقرير المطلوب من النظام:", main_menu(), chat_id)
    elif data.startswith("menu:"):
        menu = parts[1]
        if menu in {"sales", "purchases", "profits", "expenses"}: send("اختر الفترة:", period_menu(menu), chat_id)
        elif menu in {"customers", "suppliers"}:
            title, keyboard = list_menu("customer" if menu == "customers" else "supplier"); send(title, keyboard, chat_id)
    elif data == "report:inventory": inventory_pdf(chat_id)
    elif parts[0] == "report":
        action, period = parts[1], parts[2]
        if action == "sales": sales_report(period, chat_id)
        elif action == "purchases": purchases_report(period, chat_id)
        elif action == "profits": profit_report(period, chat_id)
        elif action == "expenses": expenses_report(period, chat_id)
    elif parts[0] == "list":
        title, keyboard = list_menu(parts[1], int(parts[2])); send(title, keyboard, chat_id)
    elif parts[0] == "search": PENDING_SEARCH[chat_id] = parts[1]; send("اكتب جزءًا من الاسم للبحث:", back_menu(), chat_id)
    elif parts[0] == "select": send("اختر الفترة المطلوبة:", account_period_menu(parts[1], parts[2]), chat_id)
    elif parts[0] == "statement": statement(parts[1], parts[2], parts[3], chat_id)


def _run_callback(data, chat_id):
    try:
        handle_callback(data, chat_id)
    except Exception as exc:
        send(f"تعذر إنشاء التقرير: {str(exc)[:300]}", back_menu(), chat_id)


def configure_commands():
    api("setMyCommands", {"commands": json.dumps([{"command": "menu", "description": "القائمة الرئيسية"}, {"command": "inventory", "description": "جرد المخزون PDF"}], ensure_ascii=False)})
    logger.info("Telegram commands configured; database_backend=%s", DB_BACKEND)


def main():
    offset = 0
    configure_commands()
    logger.info("Telegram reports bot started; polling enabled")
    while True:
        try:
            for update in api("getUpdates", {"timeout": 45, "offset": offset}) or []:
                offset = update["update_id"] + 1; handle(update)
        except Exception as exc:
            logger.error("Telegram polling error; retrying: %s", str(exc)[:300]); time.sleep(5)

if __name__ == "__main__": main()
