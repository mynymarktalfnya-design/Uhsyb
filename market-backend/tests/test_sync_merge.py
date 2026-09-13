import os
import sys
import tempfile
import unittest

os.environ.setdefault("ALLOW_MONGOMOCK", "true")
os.environ.setdefault("NEON_DATABASE_URL", "")
os.environ.setdefault("MONGO_URL", "")
os.environ["LOCAL_DB_FILE"] = os.path.join(tempfile.gettempdir(), "mm-sync-test.json.gz")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import _use_mock_mongo
from routes.sync import _merge_database


class SyncMergeTest(unittest.TestCase):
    def test_merges_local_records_without_deleting_remote_records(self):
        db = _use_mock_mongo()["sync_test"]
        db["products"].insert_one({"_id": "remote-only", "name": "Remote"})

        inserted, updated, skipped = _merge_database(db, {
            "products": [
                {"_id": "local-only", "name": "Local"},
            ],
        })

        self.assertEqual((inserted, updated, skipped), (1, 0, 0))
        self.assertIsNotNone(db["products"].find_one({"_id": "remote-only"}))
        self.assertIsNotNone(db["products"].find_one({"_id": "local-only"}))


if __name__ == "__main__":
    unittest.main()
