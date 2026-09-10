import os
import sys
from pathlib import Path

os.environ.pop("NEON_DATABASE_URL", None)
os.environ.pop("MONGO_URL", None)
os.environ["ALLOW_MONGOMOCK"] = "true"
sys.path.insert(0, str(Path(__file__).parents[1]))

from routes import telegram


def test_report_buttons_dispatch_pdf_documents_and_sales_text(monkeypatch):
    sent_documents = []
    sent_messages = []

    def fake_document(content, filename, caption, chat_id):
        sent_documents.append((content, filename, caption, chat_id))
        return {"ok": True}

    def fake_message(text, chat_id, with_menu=False):
        sent_messages.append((text, chat_id, with_menu))
        return {"ok": True}

    monkeypatch.setattr(telegram, "send_document", fake_document)
    monkeypatch.setattr(telegram, "send_message", fake_message)
    monkeypatch.setattr(telegram, "_text_report", lambda kind, period: f"Report {kind} {period}")
    monkeypatch.setattr(telegram, "_inventory_pdf", lambda: b"%PDF-1.4 inventory")

    for button in [
        telegram.BUTTONS["inventory"],
        telegram.BUTTONS["purchases_month"],
        telegram.BUTTONS["sales_month"],
        telegram.BUTTONS["expenses_month"],
    ]:
        telegram._handle_text("test-chat", button)

    assert len(sent_documents) == 3
    assert all(item[0].startswith(b"%PDF") for item in sent_documents)
    assert {item[3] for item in sent_documents} == {"test-chat"}
    assert any("inventory" in item[1] for item in sent_documents)
    assert any("purchases_month" in item[1] for item in sent_documents)
    assert any("expenses_month" in item[1] for item in sent_documents)
    assert sent_messages == [("Report sales month", "test-chat", True)]
