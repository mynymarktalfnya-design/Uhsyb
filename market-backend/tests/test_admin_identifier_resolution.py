import os
import sys
from pathlib import Path

os.environ.pop("NEON_DATABASE_URL", None)
os.environ.pop("MONGO_URL", None)
os.environ["ALLOW_MONGOMOCK"] = "true"
sys.path.insert(0, str(Path(__file__).parents[1]))
from routes.auth import _find_login_user


class FakeUsers:
    def __init__(self, rows):
        self.rows = rows

    def find_one(self, query):
        for row in self.rows:
            if all(row.get(key) == value for key, value in query.items()):
                return row
        return None


class FakeDb:
    def __init__(self, rows):
        self.users = FakeUsers(rows)

    def __getitem__(self, collection):
        return self.users


def test_admin_short_identifier_prefers_configured_email_record(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "owner@example.com")
    stale = {"_id": "stale", "username": "admin", "email": "old@example.com", "role": "admin", "deleted_at": None}
    configured = {"_id": "configured", "username": "admin", "email": "owner@example.com", "role": "admin", "deleted_at": None}
    selected = _find_login_user(FakeDb([stale, configured]), "admin")
    assert selected["_id"] == "configured"


def test_regular_email_and_username_resolution_remain_supported(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "owner@example.com")
    user = {"_id": "cashier", "username": "cashier", "email": "cashier@example.com", "role": "cashier", "deleted_at": None}
    db = FakeDb([user])
    assert _find_login_user(db, "cashier@example.com")["_id"] == "cashier"
    assert _find_login_user(db, "cashier")["_id"] == "cashier"
