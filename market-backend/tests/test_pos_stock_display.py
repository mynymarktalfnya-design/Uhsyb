from pathlib import Path

POS = Path(__file__).resolve().parents[2] / "artifacts" / "market-frontend" / "src" / "pages" / "POS.jsx"

def test_pos_hides_available_stock_but_keeps_out_of_stock_barcode_alert():
    source = POS.read_text(encoding="utf-8")
    assert "title: '⛔ نفد المخزون'" in source
    assert "نفد المخزون" in source
    assert "غير متوفر حاليًا" in source
    assert "variant: 'destructive'" in source
    assert "lastBarcodeRef.current = ''" in source
    assert "${fmt(p.current_stock)} متوفر" not in source
    assert "${fmt(p.current_stock)} متاح" not in source
    assert "current_stock <= 3" not in source
