"""One-time, fail-closed migration from a verified SQLite backup to PostgreSQL.

Run against a *new, empty* PostgreSQL schema only. This script never deletes
source data or truncates the destination. Run with a secured DATABASE_URL and
DONCHI_SESSION_SECRET, after reviewing the source backup.

  DONCHI_DB_ENGINE=postgres DATABASE_URL=... DONCHI_SESSION_SECRET=... \
    python migrate_sqlite_to_postgres.py /secure/backup.sqlite3
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path


def migrate(source_file: Path):
    if os.environ.get('DONCHI_DB_ENGINE') != 'postgres':
        raise RuntimeError('Set DONCHI_DB_ENGINE=postgres explicitly')
    if not source_file.is_file():
        raise RuntimeError('SQLite backup file not found')

    # Database initialization is additive: creates missing PostgreSQL tables,
    # but never resets live data. Do not run hosted_bootstrap here.
    os.environ['DONCHI_MIGRATION_MODE'] = '1'
    import server

    source = sqlite3.connect(f'file:{source_file.resolve()}?mode=ro', uri=True)
    source.row_factory = sqlite3.Row
    try:
        if source.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('Source SQLite backup failed integrity check')
        table_rows = source.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
        names = [row['name'] for row in table_rows]
        if not names or 'stores' not in names or 'users' not in names:
            raise RuntimeError('Invalid DONCHI backup: required tables missing')

        # SQLite FK order is not guaranteed, sort tables by dependencies.
        remaining = set(names)
        order = []
        while remaining:
            ready = sorted(table for table in remaining if not any(
                ref[2] in remaining and ref[2] != table
                for ref in source.execute(f'PRAGMA foreign_key_list("{table}")')))
            if not ready:
                raise RuntimeError('Cyclic SQLite foreign-key references')
            order.extend(ready)
            remaining.difference_update(ready)

        with server.connection(write=True) as target:
            # No merging with populated data: the wrong destination must fail
            # before even the first INSERT.
            for table in names:
                if not table.replace('_', '').isalnum():
                    raise RuntimeError('Unexpected source table name')
                if not target.execute('SELECT 1 FROM information_schema.tables '
                                      'WHERE table_schema=current_schema() AND table_name=?', (table,)).fetchone():
                    raise RuntimeError(f'Target schema missing {table}; update DONCHI code before migration')
                if target.execute(f'SELECT 1 FROM "{table}" LIMIT 1').fetchone():
                    raise RuntimeError(f'Target {table} is not empty — migration stopped safely')

            imported = {}
            for table in order:
                cols = [r[1] for r in source.execute(f'PRAGMA table_info("{table}")')]
                # Existing old backups can omit newly-added additive columns.
                existing = [col for col in cols if target.has_column(table, col)]
                if len(existing) != len(cols):
                    raise RuntimeError(f'Target {table} lacks source columns; migration stopped')
                quoted = ','.join('"'+col+'"' for col in existing)
                placeholders = ','.join('?' for _ in existing)
                query = f'INSERT INTO "{table}" ({quoted}) VALUES ({placeholders})'
                count = 0
                for row in source.execute(f'SELECT {quoted} FROM "{table}"'):
                    target.execute(query, tuple(row))
                    count += 1
                imported[table] = count
        print('Migration committed:', {name: imported.get(name, 0) for name in
                                     ('stores','users','products','sales','customers','debt_payments')})
        return imported
    finally:
        source.close()


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python migrate_sqlite_to_postgres.py /path/to/backup.sqlite3')
    migrate(Path(sys.argv[1]))
