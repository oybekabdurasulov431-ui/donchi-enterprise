"""No-production-data regression tests for DONCHI backups and migration preflight."""
from __future__ import annotations
import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.backup_guard import backup, restore_to_new_path, verify, sha256_file
from scripts.postgres_preflight import inventory
from operational_metrics import record, snapshot


class DataProtectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="donchi-data-tests-")
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.source = self.folder / "live.sqlite3"
        self.archive = self.folder / "backup.sqlite3"
        self.restored = self.folder / "restored.sqlite3"
        with sqlite3.connect(self.source) as db:
            db.execute("PRAGMA foreign_keys=ON")
            db.executescript("""
                CREATE TABLE stores(id TEXT PRIMARY KEY,name TEXT NOT NULL);
                CREATE TABLE products(id TEXT PRIMARY KEY,store_id TEXT REFERENCES stores(id),price REAL NOT NULL);
                CREATE TABLE customers(id TEXT PRIMARY KEY,store_id TEXT REFERENCES stores(id));
                INSERT INTO stores VALUES('shop1','Demo Shop');
                INSERT INTO products VALUES('p1','shop1',12500);
                INSERT INTO customers VALUES('c1','shop1');
            """)
            db.commit()

    def test_backup_checksum_and_restore_is_create_only(self):
        original = self.source.read_bytes()
        result = backup(self.source, self.archive)
        self.assertEqual(result["integrity"], "ok")
        self.assertEqual(result["foreign_keys"], "ok")
        self.assertTrue(self.archive.with_suffix(".sqlite3.sha256").is_file())
        self.assertEqual(sha256_file(self.archive), result["sha256"])
        self.assertEqual(self.source.read_bytes(), original, "Backup altered source database")
        restored = restore_to_new_path(self.archive, self.restored)
        self.assertEqual(restored["schema_sha256"], result["schema_sha256"])
        with sqlite3.connect(self.restored) as db:
            self.assertEqual(db.execute("SELECT price FROM products WHERE id='p1'").fetchone()[0],12500)
        with self.assertRaises(FileExistsError):
            restore_to_new_path(self.archive, self.restored)
        with self.assertRaises(FileExistsError):
            backup(self.source, self.archive)

    def test_checksum_mismatch_refuses_restore(self):
        backup(self.source, self.archive)
        with self.archive.open("ab") as f:
            f.write(b"invalid")
        with self.assertRaisesRegex(ValueError,"checksum"):
            restore_to_new_path(self.archive,self.restored)
        self.assertFalse(self.restored.exists())

    def test_missing_sidecar_refuses_restore(self):
        backup(self.source,self.archive)
        self.archive.with_suffix(".sqlite3.sha256").unlink()
        with self.assertRaises(FileNotFoundError):
            restore_to_new_path(self.archive,self.restored)
        self.assertFalse(self.restored.exists())

    def test_foreign_key_violation_fails_closed(self):
        with sqlite3.connect(self.source) as db:
            db.execute("PRAGMA foreign_keys=OFF")
            db.execute("INSERT INTO products VALUES('orphan','missing',1)")
        with self.assertRaisesRegex(ValueError,"foreign key"):
            verify(self.source)
        with self.assertRaisesRegex(ValueError,"foreign key"):
            backup(self.source,self.archive)
        self.assertFalse(self.archive.exists())

    def test_preflight_read_only_and_reports_remaining_work(self):
        source_bytes = self.source.read_bytes()
        result = inventory(self.source)
        self.assertEqual(result["database_integrity"],"ok")
        self.assertFalse(result["postgresql_connected"])
        self.assertFalse(result["migration_executed"])
        self.assertEqual(result["readiness"],"manual_schema_conversion_required")
        self.assertIn("sales",result["missing_expected_tables"])
        self.assertEqual(next(x for x in result["tables"] if x["name"]=="products")["row_count"],1)
        self.assertEqual(source_bytes,self.source.read_bytes())

    def test_metrics_do_not_store_urls_or_sensitive_payloads(self):
        marker="PRIVATE-ACCOUNT-DO-NOT-LOG"
        record("POST",500,2600.0,"a1b2c3d4e5f60708")
        record("GET",200,12.0,"aa00bb11cc22dd33")
        report=snapshot()
        self.assertGreaterEqual(report["request_counts"]["5xx"],1)
        self.assertEqual(report["recent_server_errors"][0]["status"],500)
        self.assertNotIn(marker,json.dumps(report))
        self.assertNotIn("request_body",json.dumps(report))
        self.assertFalse(any("url" in x or "headers" in x for x in report["recent_server_errors"]))


if __name__=="__main__":
    unittest.main(verbosity=2)
