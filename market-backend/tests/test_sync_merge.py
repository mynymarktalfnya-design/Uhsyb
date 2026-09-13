import os
import sys
import tempfile
import unittest

os.environ["ALLOW_MONGOMOCK"] = "true"
os.environ["NEON_DATABASE_URL"] = ""
os.environ["MONGO_URL"] = ""
os.environ["LOCAL_DB_FILE"] = os.path.join(tempfile.gettempdir(), "mm-sync-test.json.gz")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import _use_mock_mongo
from routes.sync import _merge_database, resolve_conflict


class SyncMergeTest(unittest.TestCase):
    def setUp(self):
        self.db = _use_mock_mongo()[f"sync_test_{id(self)}"]

    def test_merges_local_records_without_deleting_remote_records(self):
        self.db["products"].insert_one({"_id": "remote-only", "name": "Remote"})
        inserted, updated, skipped, conflicts = _merge_database(self.db, {
            "products": [{"_id": "local-only", "name": "Local"}],
        })
        self.assertEqual((inserted, updated, skipped, conflicts), (1, 0, 0, 0))
        self.assertIsNotNone(self.db["products"].find_one({"_id": "remote-only"}))
        self.assertIsNotNone(self.db["products"].find_one({"_id": "local-only"}))

    def test_records_conflict_and_local_resolution(self):
        self.db["products"].insert_one({"_id": "same", "name": "Remote", "updated_at": "2026-09-13T10:00:00+00:00"})
        result = _merge_database(self.db, {
            "products": [{"_id": "same", "name": "Local", "updated_at": "2026-09-13T11:00:00+00:00"}],
        })
        self.assertEqual(result, (0, 0, 1, 1))
        conflict = self.db["sync_conflicts"].find_one({"status": "pending"})
        self.assertEqual(conflict["suggested_resolution"], "local")

        response = resolve_conflict(
            conflict["_id"], {"resolution": "local"}, self.db,
            {"_id": "admin", "role": "admin"},
        )
        self.assertEqual(response["status"], "resolved")
        self.assertEqual(self.db["products"].find_one({"_id": "same"})["name"], "Local")
        self.assertEqual(self.db["sync_conflicts"].find_one({"_id": conflict["_id"]})["status"], "resolved")


if __name__ == "__main__":
    unittest.main()
