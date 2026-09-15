import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import mmf_local_service as service


class LocalQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False)
        self.tmp.close()
        os.unlink(self.tmp.name)
        service.DB_PATH = self.tmp.name

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(self.tmp.name + suffix)
            except FileNotFoundError:
                pass

    def test_enqueue_is_durable_and_idempotent(self):
        first = service.enqueue({
            "operation_id": "op-1", "url": "http://127.0.0.1:9/unreachable",
            "method": "POST", "body": {"total": 10}, "headers": {},
        })
        second = service.enqueue({
            "operation_id": "op-1", "url": "http://127.0.0.1:9/unreachable",
            "method": "POST", "body": {"total": 999}, "headers": {},
        })
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["operation_id"], "op-1")
        self.assertEqual(service.list_operations()[0]["state"], "pending")

    def test_failed_operation_is_retained_for_retry(self):
        row = service.enqueue({
            "operation_id": "op-2", "url": "http://127.0.0.1:9/unreachable",
            "method": "POST", "body": {"total": 20}, "headers": {},
        })
        self.assertFalse(service.sync_one(row))
        stored = service.list_operations()[0]
        self.assertEqual(stored["state"], "failed")
        self.assertEqual(stored["retries"], 1)
        self.assertTrue(stored["last_error"])

    def test_raw_authorization_is_not_stored_in_headers(self):
        service.enqueue({
            "operation_id": "op-secret", "url": "http://127.0.0.1:9/unreachable",
            "method": "POST", "body": {},
            "headers": {"Authorization": "Bearer raw-secret-token"},
        })
        stored = service.list_operations()[0]
        self.assertNotIn("raw-secret-token", stored["headers"])
        self.assertNotIn("Authorization", stored["headers"])

    def test_sync_does_not_send_row_claimed_by_another_worker(self):
        row = service.enqueue({
            "operation_id": "op-claimed", "url": "http://127.0.0.1:9/unreachable",
            "method": "POST", "body": {}, "headers": {},
        })
        with service._db_lock:
            conn = service.db()
            conn.execute("UPDATE operations SET state='syncing' WHERE id=?", (row["id"],))
            conn.commit(); conn.close()
        self.assertIsNone(service.sync_one(row))
        self.assertEqual(service.list_operations()[0]["state"], "syncing")


if __name__ == "__main__":
    unittest.main()
