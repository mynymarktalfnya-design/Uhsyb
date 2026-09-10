import ast
from pathlib import Path


TELEGRAM = Path(__file__).resolve().parents[1] / "routes" / "telegram.py"
CUSTOMER_PAGE = Path(__file__).resolve().parents[2] / "artifacts" / "market-frontend" / "src" / "pages" / "CustomerDetail.jsx"
SUPPLIER_PAGE = Path(__file__).resolve().parents[2] / "artifacts" / "market-frontend" / "src" / "pages" / "SupplierDetail.jsx"
SUPPLIER_SUMMARY_PAGE = Path(__file__).resolve().parents[2] / "artifacts" / "market-frontend" / "src" / "pages" / "SupplierSummaryStatement.jsx"
PDF_EXPORT = Path(__file__).resolve().parents[2] / "artifacts" / "market-frontend" / "src" / "lib" / "pdfExport.js"


def _source():
    return TELEGRAM.read_text(encoding="utf-8")


def test_sales_are_text_only_and_other_reports_are_pdf():
    tree = ast.parse(_source())
    calls = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_send_requested_report":
            kind = node.args[1].value
            period = node.args[2].value
            as_pdf = next(keyword.value.value for keyword in node.keywords if keyword.arg == "as_pdf")
            calls[(kind, period)] = as_pdf
    assert calls[("sales", "today")] is False
    assert calls[("sales", "month")] is False
    assert calls[("purchases", "today")] is True
    assert calls[("purchases", "month")] is True
    assert calls[("expenses", "today")] is True
    assert calls[("expenses", "month")] is True
    assert "send_document(_inventory_pdf()" in _source()


def test_customer_and_supplier_pages_keep_system_pdf_exports():
    customer = CUSTOMER_PAGE.read_text(encoding="utf-8")
    supplier = SUPPLIER_PAGE.read_text(encoding="utf-8")
    supplier_summary = SUPPLIER_SUMMARY_PAGE.read_text(encoding="utf-8")
    assert "exportStatementPDF" in customer
    assert "exportStatementPDF" in supplier
    assert "window.print()" in supplier_summary
    assert "طباعة" in supplier_summary
    assert "exportSupplierSummaryPDF" in supplier_summary
    for field in ("supplier", "summary", "movements: data.movements || []", "period: data.period", "reportNo: data.report_no", "issuedAt: data.issued_at"):
        assert field in supplier_summary
    pdf_export = PDF_EXPORT.read_text(encoding="utf-8")
    assert "export async function exportSupplierSummaryPDF" in pdf_export
    for column in ("تاريخ الحركة", "نوع الحركة", "رقم الفاتورة", "رقم الدفعة", "المبلغ", "الرصيد"):
        assert column in pdf_export
    for total in ("إجمالي عدد الفواتير", "إجمالي قيمة فواتير الشراء", "إجمالي عدد الدفعات", "إجمالي الدفعات للتاجر", "المستحق للتاجر"):
        assert total in pdf_export
    assert "exportStatementPDF({" in customer
    assert "exportStatementPDF({" in supplier
    assert "kind: 'customer'" in customer
    assert "kind: 'supplier'" in supplier
