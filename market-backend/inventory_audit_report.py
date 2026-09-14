"""Shared inventory-audit data and PDF renderer for the API and Telegram bot."""
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.pdfgen import canvas as canvas_module

from database import C

FONT_PATH = "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf"
FONT_BOLD_PATH = "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf"
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
        self.drawCentredString(A4[0] / 2, 8 * mm, f"ميني ماركت الفنية   |   صفحة {self._pageNumber} من {total}")
        self.restoreState()


def _barcode(db, product_id):
    row = db[C.barcodes].find_one({"product_id": product_id}, {"barcode": 1}, sort=[("is_primary", -1)])
    return row.get("barcode") if row else "—"


def build_inventory_snapshot(db, *, audit_no, actor_name, branch="ميني ماركت الفنية", actual_by_product=None, created_at=None):
    created_at = created_at or datetime.now(timezone.utc)
    actual_by_product = actual_by_product or {}
    rows = []
    for index, product in enumerate(db[C.products].find({"deleted_at": None, "is_active": True}).sort("name", 1), 1):
        pid = product["_id"]
        system_qty = float(product.get("current_stock", 0) or 0)
        actual = actual_by_product.get(pid, system_qty)
        rows.append({
            "line_no": index,
            "product_id": pid,
            "barcode": _barcode(db, pid),
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
    return Paragraph(str(text).replace("&", "&amp;"), style)


def render_inventory_pdf(snapshot):
    out = BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, rightMargin=12 * mm, leftMargin=12 * mm, topMargin=12 * mm, bottomMargin=16 * mm, title="جرد المخزون - ميني ماركت الفنية")
    styles = getSampleStyleSheet()
    normal = ParagraphStyle("InventoryNormal", parent=styles["Normal"], fontName=FONT, fontSize=8, leading=11, alignment=TA_RIGHT)
    bold = ParagraphStyle("InventoryBold", parent=normal, fontName=FONT_BOLD, fontSize=10, leading=13)
    title = ParagraphStyle("InventoryTitle", parent=bold, fontSize=16, leading=20, alignment=TA_RIGHT)
    story = [_p("ميني ماركت الفنية", title), _p("كشف جرد المخزون", bold), Spacer(1, 4)]
    dt = snapshot["created_at"].astimezone(timezone.utc)
    meta = [[_p("رقم الجرد", bold), _p(snapshot["audit_no"], normal), _p("التاريخ والوقت", bold), _p(dt.strftime("%Y-%m-%d %H:%M UTC"), normal)],
            [_p("المستودع / الفرع", bold), _p(snapshot["branch"], normal), _p("مسؤول الجرد", bold), _p(snapshot["actor_name"], normal)]]
    meta_table = Table(meta, colWidths=[28*mm, 52*mm, 28*mm, 72*mm], repeatRows=2)
    meta_table.setStyle(TableStyle([("GRID", (0,0), (-1,-1), .35, colors.grey), ("BACKGROUND", (0,0), (-1,-1), colors.whitesmoke), ("VALIGN", (0,0), (-1,-1), "MIDDLE")]))
    story += [meta_table, Spacer(1, 8)]
    headers = ["م", "الباركود (كود المنتج)", "اسم المنتج", "الوحدة", "الكمية الفعلية", "كمية النظام", "تكلفة الوحدة"]
    data = [[_p(h, bold) for h in headers]]
    for row in snapshot["rows"]:
        data.append([_p(row["line_no"], normal), _p(row["barcode"], normal), _p(row["name"], normal), _p(row["unit"], normal), _p(f'{row["actual_quantity"]:,.2f}', normal), _p(f'{row["system_quantity"]:,.2f}', normal), _p(f'{row["unit_cost"]:,.2f}', normal)])
    table = Table(data, colWidths=[9*mm, 31*mm, 48*mm, 20*mm, 27*mm, 27*mm, 25*mm], repeatRows=1, splitByRow=1)
    table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#0f2948")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .3, colors.grey), ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("ALIGN", (0,0), (-1,-1), "RIGHT"), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]), ("FONTNAME", (0,0), (-1,-1), FONT)]))
    story += [table, Spacer(1, 8)]
    totals = [[_p("إجمالي عدد الأصناف", bold), _p(snapshot["total_items"], normal), _p("إجمالي الكمية الفعلية", bold), _p(f'{snapshot["total_actual"]:,.2f}', normal), _p("إجمالي كمية النظام", bold), _p(f'{snapshot["total_system"]:,.2f}', normal)]]
    totals_table = Table(totals, colWidths=[31*mm, 18*mm, 35*mm, 20*mm, 31*mm, 20*mm])
    totals_table.setStyle(TableStyle([("GRID", (0,0), (-1,-1), .35, colors.grey), ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#fef3c7"))]))
    story += [totals_table, Spacer(1, 8), _p("ملاحظات الجرد", bold), Spacer(1, 14)]
    signatures = [[_p("مسؤول الجرد:", bold), _p("الاسم: ____________________\nالتوقيع: ____________________\nالتاريخ: ____________________", normal)], [_p("المراجع:", bold), _p("الاسم: ____________________\nالتوقيع: ____________________\nالتاريخ: ____________________", normal)], [_p("مدير النظام:", bold), _p("الاسم: ____________________\nالتوقيع: ____________________\nالتاريخ: ____________________", normal)]]
    story.append(Table(signatures, colWidths=[35*mm, 140*mm], rowHeights=[18*mm]*3, style=[("GRID", (0,0), (-1,-1), .35, colors.grey), ("VALIGN", (0,0), (-1,-1), "TOP")]))
    doc.build(story, canvasmaker=_NumberedCanvas)
    return out.getvalue()
