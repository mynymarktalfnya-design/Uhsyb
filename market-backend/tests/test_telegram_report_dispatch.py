import os
import sys
from pathlib import Path

os.environ.pop("NEON_DATABASE_URL", None)
os.environ.pop("MONGO_URL", None)
os.environ["ALLOW_MONGOMOCK"] = "true"
sys.path.insert(0, str(Path(__file__).parents[1]))

from routes import telegram


def test_report_buttons_dispatch_pdf_documents(monkeypatch):
    sent = []

    def fake_document(content, filename, caption, chat_id):
        sent.append((content, filename, caption, chat_id))
        return {"ok": True}

    monkeypatch.setattr(telegram, "send_document", fake_document)
    monkeypatch.setattr(telegram, "_text_report", lambda kind, period: f"Report {kind} {period}")
    monkeypatch.setattr(telegram, "_inventory_pdf", lambda: b"%PDF-1.4 inventory")

    for button in [
        telegram.BUTTONS["inventory"],
        telegram.BUTTONS["purchases_month"],
        telegram.BUTTONS["sales_month"],
        telegram.BUTTONS["expenses_month"],
    ]:
        telegram._handle_text("test-chat", button)

    assert len(sent) == 4
    assert all(item[0].startswith(b"%PDF") for item in sent)
    assert {item[3] for item in sent} == {"test-chat"}
    assert any("inventory" in item[1] for item in sent)
    assert any("purchases_month" in item[1] for item in sent)
    assert any("sales_month" in item[1] for item in sent)
    assert any("expenses_month" in item[1] for item in sent)
