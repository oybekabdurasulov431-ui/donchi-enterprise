"""Safely transfer every SQLite row to a separately namespaced PostgreSQL archive.

This is an INTERMEDIATE migration stage, NOT a PostgreSQL backend switch.
Each source row becomes a JSONB record in the PostgreSQL schema
'donchi_migration_stage', retaining SQLite table/column names and row order.
No application/public tables are created or changed.

Requirements: pip install "psycopg[binary]>=3.2,<4"
Usage in a PRIVATE shell that can access both the SQLite backup and DATABASE_URL:
    python scripts/stage_sqlite_to_postgres.py --sqlite /secure-backup/donchi.sqlite3 --dry-run
    python scripts/stage_sqlite_to_postgres.py --sqlite /secure-backup/donchi.sqlite3 --apply

The apply command refuses to overwrite an existing staged dataset.
DB passwords, row contents, personal/customer data are never printed.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def source_backup(path: Path):
    path=path.resolve(strict=True)
    if not path.is_file():
        raise RuntimeError("SQLite snapshot does not exist")
    db=sqlite3.connect("file:"+path.as_posix()+"?mode=ro",uri=True)
    db.row_factory=sqlite3.Row
    try:
        if db.execute("PRAGMA quick_check(1)").fetchone()[0]!="ok":
            raise RuntimeError("Backup integrity check failed")
        tables=[r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        counts={}
        for name in tables:
            quoted='"'+name.replace('"','""')+'"'
            counts[name]=db.execute("SELECT COUNT(*) FROM "+quoted).fetchone()[0]
        return db,tables,counts
    except BaseException:
        db.close()
        raise


def encode_value(value):
    if isinstance(value,bytes):
        return {"__sqlite_blob_base64__":base64.b64encode(value).decode("ascii")}
    return value


def migration_id(tables,counts,source):
    digest=hashlib.sha256()
    for table in tables:
        quoted='"'+table.replace('"','""')+'"'
        digest.update(json.dumps([table,counts[table]],ensure_ascii=False).encode())
        # This is intentionally a logical dataset fingerprint, not the physical file's checksum.
        for row in source.execute("SELECT * FROM "+quoted+" ORDER BY rowid"):
            digest.update(json.dumps([encode_value(v) for v in row],
                         ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8"))
            digest.update(b"\n")
    return digest.hexdigest()


def stage(sqlite_file:Path,apply=False):
    sqlite_db,tables,counts=source_backup(sqlite_file)
    try:
        fingerprint=migration_id(tables,counts,sqlite_db)
        summary={"fingerprint":fingerprint,"table_count":len(tables),
                 "record_count":sum(counts.values()),"dry_run":not apply}
        if not apply:
            return summary
        url=os.environ.get("DATABASE_URL")
        if not url:
            raise RuntimeError("DATABASE_URL is missing")
        try:
            import psycopg
            from psycopg.types.json import Jsonb
        except ImportError:
            raise RuntimeError('Install psycopg[binary] before applying the staging archive') from None
        try:
            with psycopg.connect(url,connect_timeout=8) as pg:
                with pg.cursor() as cur:
                    cur.execute("CREATE SCHEMA IF NOT EXISTS donchi_migration_stage")
                    cur.execute("""CREATE TABLE IF NOT EXISTS donchi_migration_stage.snapshots (
                        fingerprint TEXT PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL,
                        manifest JSONB NOT NULL, completed BOOLEAN NOT NULL DEFAULT FALSE)""")
                    cur.execute("""CREATE TABLE IF NOT EXISTS donchi_migration_stage.records (
                        fingerprint TEXT NOT NULL REFERENCES donchi_migration_stage.snapshots(fingerprint),
                        table_name TEXT NOT NULL, row_number BIGINT NOT NULL, payload JSONB NOT NULL,
                        PRIMARY KEY(fingerprint,table_name,row_number))""")
                    cur.execute("SELECT 1 FROM donchi_migration_stage.snapshots WHERE fingerprint=%s",(fingerprint,))
                    if cur.fetchone():
                        raise RuntimeError("Dataset already staged; no changes made")
                    cur.execute("INSERT INTO donchi_migration_stage.snapshots VALUES (%s,%s,%s,FALSE)",
                        (fingerprint,datetime.now(timezone.utc),Jsonb({"table_counts":counts})))
                    for table in tables:
                        quoted='"'+table.replace('"','""')+'"'
                        for i,row in enumerate(sqlite_db.execute("SELECT * FROM "+quoted+" ORDER BY rowid")):
                            item={name:encode_value(row[name]) for name in row.keys()}
                            cur.execute("""INSERT INTO donchi_migration_stage.records
                                (fingerprint,table_name,row_number,payload) VALUES (%s,%s,%s,%s)""",
                                (fingerprint,table,i,Jsonb(item)))
                    cur.execute("""SELECT table_name,COUNT(*) FROM donchi_migration_stage.records
                        WHERE fingerprint=%s GROUP BY table_name""",(fingerprint,))
                    imported=dict(cur.fetchall())
                    if any(imported.get(t,0)!=counts[t] for t in tables) or len(imported)!=len([t for t in tables if counts[t]>0]):
                        raise RuntimeError("Row count verification failed: rollback")
                    cur.execute("""UPDATE donchi_migration_stage.snapshots
                        SET completed=TRUE WHERE fingerprint=%s""",(fingerprint,))
                pg.commit()
        except RuntimeError:
            raise
        except Exception:
            # Do not expose connection details or database content in public errors.
            raise RuntimeError("PostgreSQL archive failed; transaction not committed") from None
        return summary|{"archive_verified":True}
    finally:
        sqlite_db.close()


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--sqlite",required=True,type=Path)
    mode=ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run",action="store_true")
    mode.add_argument("--apply",action="store_true")
    args=ap.parse_args()
    print(json.dumps(stage(args.sqlite,apply=args.apply),ensure_ascii=False,indent=2))
