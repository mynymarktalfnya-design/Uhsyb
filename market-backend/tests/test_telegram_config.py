import ast
import os
from pathlib import Path


_SOURCE = Path(__file__).parents[1] / "routes" / "telegram.py"
_TREE = ast.parse(_SOURCE.read_text())
_CHAT_ID_NODE = next(
    node for node in _TREE.body
    if isinstance(node, ast.FunctionDef) and node.name == "_chat_id"
)
_NAMESPACE = {"os": os}
exec(compile(ast.Module(body=[_CHAT_ID_NODE], type_ignores=[]), str(_SOURCE), "exec"), _NAMESPACE)
_chat_id = _NAMESPACE["_chat_id"]


def test_chat_id_supports_canonical_name(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "canonical")
    monkeypatch.setenv("TELEGRAMCHATID", "legacy")
    assert _chat_id() == "canonical"


def test_chat_id_supports_legacy_name(monkeypatch):
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setenv("TELEGRAMCHATID", "legacy")
    assert _chat_id() == "legacy"
