from pathlib import Path

REPORTS = Path(__file__).resolve().parents[2] / "artifacts" / "market-frontend" / "src" / "pages" / "Reports.jsx"
PDF = Path(__file__).resolve().parents[2] / "artifacts" / "market-frontend" / "src" / "lib" / "pdfExport.js"


def test_monthly_financial_print_uses_real_daily_rows_and_blocks_empty_months():
    source = REPORTS.read_text(encoding="utf-8")
    assert "لا توجد عمليات لهذا الشهر" in source
    assert "اختر شهرًا يحتوي على مبيعات أو مشتريات أو مصروفات" in source
    assert "const daily = Array.isArray(month?.daily) ? month.daily : [];" in source
    assert "const sumDaily = (key)" in source
    assert "const salesTotal = total('sales_total');" in source


def test_monthly_financial_pdf_is_explicitly_rtl():
    source = PDF.read_text(encoding="utf-8")
    assert '<div dir="rtl" style="padding:0 0 18px;background:#fff;">' in source
    assert '<table dir="rtl" style="width:100%;border-collapse:collapse;">' in source
