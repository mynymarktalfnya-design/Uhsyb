from pathlib import Path


SOURCE = (Path(__file__).parents[1] / "routes" / "telegram.py").read_text()


def test_sales_buttons_are_text_and_other_reports_are_pdf():
    assert '_send_requested_report(chat_id, "sales", "today", as_pdf=False)' in SOURCE
    assert '_send_requested_report(chat_id, "sales", "month", as_pdf=False)' in SOURCE
    assert '_send_requested_report(chat_id, "purchases", "month", as_pdf=True)' in SOURCE
    assert '_send_requested_report(chat_id, "expenses", "month", as_pdf=True)' in SOURCE


def test_inventory_report_uses_current_stock_fields():
    assert 'product.get("current_stock", product.get("stock", product.get("quantity", 0)))' in SOURCE
    assert 'product.get("min_stock_level", product.get("min_stock", product.get("reorder_level", 0)))' in SOURCE
