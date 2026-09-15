"""Shared inventory-audit data and PDF renderer for the API and Telegram bot."""
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.pdfgen import canvas as canvas_module
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except Exception:  # pragma: no cover - optional only for minimal installs
    arabic_reshaper = None
    get_display = None

from database import C

_FONT_DIR = Path(__file__).resolve().parent / "assets" / "fonts"
FONT_PATH = str(_FONT_DIR / "NotoSansArabic-Regular.ttf") if (_FONT_DIR / "NotoSansArabic-Regular.ttf").exists() else "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf"
FONT_BOLD_PATH = str(_FONT_DIR / "NotoSansArabic-Bold.ttf") if (_FONT_DIR / "NotoSansArabic-Bold.ttf").exists() else "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf"
try:
    pdfmetrics.registerFont(TTFont("InventoryArabic", FONT_PATH))
    pdfmetrics.registerFont(TTFont("InventoryArabicBold", FONT_BOLD_PATH))
except Exception:
    pass
FONT = "InventoryArabic"
FONT_BOLD = "InventoryArabicBold"

class _NumberedCanvas(canvas_module.Canvas):
    def __init__(self, *args, **kwargs):
        canvas_module.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []
    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()
    def save(self):
        total = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_footer(total)
            canvas_module.Canvas.showPage(self)
        canvas_module.Canvas.save(self)
    def _draw_footer(self, total):
        self.saveState(); self.setFont(FONT, 8); self.setFillColor(colors.grey)
        page_width, _ = self._pagesize
        self.drawCentredString(page_width / 2, 4 * mm, _rtl(f"صفحة {self._pageNumber} من {total}"))
        self.restoreState()


def _barcodes(db, product_ids):
    """Load barcodes in one query; N+1 queries made large audits very slow."""
    rows = list(db[C.barcodes].find({"product_id": {"$in": list(product_ids)}}, {"product_id": 1, "barcode": 1, "is_primary": 1}))
    result = {}
    for row in rows:
        pid = row.get("product_id")
        if pid not in result or row.get("is_primary", False):
            result[pid] = row.get("barcode") or "—"
    return result


def build_inventory_snapshot(db, *, audit_no, actor_name, branch="ميني ماركت الفنية", actual_by_product=None, created_at=None):
    created_at = created_at or datetime.now(timezone.utc)
    actual_by_product = actual_by_product or {}
    rows = []
    products = list(db[C.products].find({"deleted_at": None, "is_active": True}).sort("name", 1))
    barcode_by_product = _barcodes(db, [product["_id"] for product in products])
    for index, product in enumerate(products, 1):
        pid = product["_id"]
        system_qty = float(product.get("current_stock", 0) or 0)
        actual = actual_by_product.get(pid, system_qty)
        rows.append({
            "line_no": index,
            "product_id": pid,
            "barcode": barcode_by_product.get(pid, "—"),
            "name": product.get("name", "—"),
            "unit": product.get("unit", "piece"),
            "actual_quantity": float(actual),
            "system_quantity": system_qty,
            "unit_cost": float(product.get("cost_price", 0) or 0),
        })
    return {
        "audit_no": audit_no, "created_at": created_at, "branch": branch,
        "actor_name": actor_name, "notes": "", "rows": rows,
        "total_items": len(rows),
        "total_actual": sum(r["actual_quantity"] for r in rows),
        "total_system": sum(r["system_quantity"] for r in rows),
    }


def _p(text, style):
    value = str(text)
    if arabic_reshaper and get_display and any("\u0600" <= ch <= "\u06ff" for ch in value):
        value = get_display(arabic_reshaper.reshape(value))
    return Paragraph(value.replace("&", "&amp;"), style)


def _rtl(text):
    value = str(text)
    if arabic_reshaper and get_display and any("\u0600" <= ch <= "\u06ff" for ch in value):
        return get_display(arabic_reshaper.reshape(value))
    return value


def render_inventory_pdf(snapshot):
    out = BytesIO()
    page = landscape(A4)
    doc = SimpleDocTemplate(out, pagesize=page, rightMargin=6 * mm, leftMargin=6 * mm, topMargin=6 * mm, bottomMargin=9 * mm, title="جرد المخزون - ميني ماركت الفنية")
    styles = getSampleStyleSheet()
    normal = ParagraphStyle("InventoryNormal", parent=styles["Normal"], fontName=FONT, fontSize=6.4, leading=7.2, alignment=TA_RIGHT, spaceAfter=0, spaceBefore=0)
    bold = ParagraphStyle("InventoryBold", parent=normal, fontName=FONT_BOLD, fontSize=7.2, leading=8.2, spaceAfter=0, spaceBefore=0)
    title = ParagraphStyle("InventoryTitle", parent=bold, fontSize=10.5, leading=11.5, alignment=TA_RIGHT)
    story = [_p("ميني ماركت الفنية — كشف جرد المخزون", title), Spacer(1, 1.5 * mm)]
    dt = snapshot["created_at"].astimezone(timezone.utc)
    meta = [[_p("رقم الجرد", bold), _p(snapshot["audit_no"], normal), _p("التاريخ والوقت", bold), _p(dt.strftime("%Y-%m-%d %H:%M UTC"), normal)],
            [_p("المستودع / الفرع", bold), _p(snapshot["branch"], normal), _p("مسؤول الجرد", bold), _p(snapshot["actor_name"], normal)]]
    meta_table = Table(meta, colWidths=[24*mm, 70*mm, 24*mm, 70*mm], repeatRows=2, rowHeights=[6.5*mm, 6.5*mm])
    meta_table.setStyle(TableStyle([("GRID", (0,0), (-1,-1), .25, colors.grey), ("BACKGROUND", (0,0), (-1,-1), colors.whitesmoke), ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("LEFTPADDING", (0,0), (-1,-1), 2), ("RIGHTPADDING", (0,0), (-1,-1), 2), ("TOPPADDING", (0,0), (-1,-1), 1), ("BOTTOMPADDING", (0,0), (-1,-1), 1)]))
    story += [meta_table, Spacer(1, 2 * mm)]
    headers = ["م", "الباركود (كود المنتج)", "اسم المنتج", "الوحدة", "الكمية الفعلية", "كمية النظام", "تكلفة الوحدة"]
    data = [[_p(h, bold) for h in headers]]
    for row in snapshot["rows"]:
        data.append([_p(row["line_no"], normal), _p(row["barcode"], normal), _p(row["name"], normal), _p(row["unit"], normal), _p(f'{row["actual_quantity"]:,.2f}', normal), _p(f'{row["system_quantity"]:,.2f}', normal), _p(f'{row["unit_cost"]:,.2f}', normal)])
    # Keep the table within A4 printable width (210 - 24 = 186 mm).
    table = Table(data, colWidths=[10*mm, 35*mm, 88*mm, 27*mm, 34*mm, 34*mm, 45*mm], repeatRows=1, splitByRow=1, rowSplitRange=(1, -1))
    table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#0f2948")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .2, colors.grey), ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("ALIGN", (0,0), (-1,-1), "RIGHT"), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]), ("FONTNAME", (0,0), (-1,-1), FONT), ("LEFTPADDING", (0,0), (-1,-1), 1.5), ("RIGHTPADDING", (0,0), (-1,-1), 1.5), ("TOPPADDING", (0,0), (-1,-1), 1), ("BOTTOMPADDING", (0,0), (-1,-1), 1)]))
    story += [table, Spacer(1, 2 * mm)]
    totals = [[_p("عدد الأصناف", bold), _p(snapshot["total_items"], normal), _p("الكمية الفعلية", bold), _p(f'{snapshot["total_actual"]:,.2f}', normal), _p("كمية النظام", bold), _p(f'{snapshot["total_system"]:,.2f}', normal)]]
    totals_table = Table(totals, colWidths=[25*mm, 20*mm, 30*mm, 25*mm, 25*mm, 25*mm], rowHeights=[7*mm])
    totals_table.setStyle(TableStyle([("GRID", (0,0), (-1,-1), .25, colors.grey), ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#fef3c7")), ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("LEFTPADDING", (0,0), (-1,-1), 2), ("RIGHTPADDING", (0,0), (-1,-1), 2)]))
    story += [totals_table, Spacer(1, 2 * mm), _p("ملاحظات الجرد: " + (snapshot.get("notes") or "—"), normal)]
    signatures = [[_p("مسؤول الجرد", bold), _p("المراجع", bold), _p("مدير النظام", bold)], [_p("الاسم: __________  التوقيع: __________  التاريخ: ______", normal), _p("الاسم: __________  التوقيع: __________  التاريخ: ______", normal), _p("الاسم: __________  التوقيع: __________  التاريخ: ______", normal)]]
    story.append(Table(signatures, colWidths=[82*mm, 82*mm, 82*mm], rowHeights=[5*mm, 8*mm], style=[("GRID", (0,0), (-1,-1), .25, colors.grey), ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("LEFTPADDING", (0,0), (-1,-1), 2), ("RIGHTPADDING", (0,0), (-1,-1), 2)]))
    doc.build(story, canvasmaker=_NumberedCanvas)
    return out.getvalue()
