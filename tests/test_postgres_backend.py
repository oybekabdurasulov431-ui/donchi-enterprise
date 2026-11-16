"""Pure PostgreSQL adapter logic; does not require a live database."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from postgres_backend import _convert_placeholders, _create_order, _Row


class PostgresAdapterTests(unittest.TestCase):
    def test_qmark_parameters_ignore_quoted_text(self):
        statement = "SELECT '?' AS literal, name FROM products WHERE id=? AND category='x''?y'"
        self.assertEqual(_convert_placeholders(statement),
                         "SELECT '?' AS literal, name FROM products WHERE id=%s AND category='x''?y'")

    def test_schema_orders_foreign_keys_before_indices(self):
        statements = [
            'CREATE TABLE IF NOT EXISTS child(id TEXT REFERENCES parent(id))',
            'CREATE INDEX IF NOT EXISTS idx_child ON child(id)',
            'CREATE TABLE IF NOT EXISTS parent(id TEXT PRIMARY KEY)',
        ]
        ordered = _create_order(statements)
        self.assertIn('parent(', ordered[0])
        self.assertIn('child(', ordered[1])
        self.assertIn('INDEX', ordered[2])

    def test_rows_support_sqlite_style_index_and_key(self):
        row = _Row({'id': 'abc', 'amount': 12})
        self.assertEqual(row['id'], row[0])
        self.assertEqual(row[1], 12)


if __name__ == '__main__': unittest.main()
