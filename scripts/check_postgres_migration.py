"""Read-only preflight for migrating DONCHI from SQLite to Railway PostgreSQL.

NO data is modified on either database. Requires psycopg 3 to inspect Postgres.
  python -m pip install "psycopg[binary]>=3.2,<4"
  DATABASE_URL=... python scripts/check_postgres_migration.py --sqlite /app/data/yempro.sqlite3

Use a private terminal (never paste or print the DATABASE_URL).
"""
from __future__ import annotations
import argparse
import json
import os
import sqlite3
from pathlib import Path


def inspect_sqlite(path: Path):
    path=path.resolve(strict=True)
    con=sqlite3.connect("file:"+path.as_posix()+"?mode=ro",uri=True)
    try:
        integrity=con.execute("PRAGMA quick_check(1)").fetchone()[0]
        if integrity!="ok":raise RuntimeError("SQLite integrity check failed")
        tables=[v[0] for v in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        rows={}
        for table in tables:
            safely_quoted='"'+table.replace('"','""')+'"'
            rows[table]=int(con.execute("SELECT COUNT(*) FROM "+safely_quoted).fetchone()[0])
        return {"integrity":integrity,"tables":rows}
    finally:con.close()


def inspect_postgres(url):
    if not url:
        return {"connected":False,"reason":"DATABASE_URL is not configured"}
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("Install psycopg[binary] for PostgreSQL preflight") from exc
    # Read-only transaction, no migrations / schema creation.
    try:
        with psycopg.connect(url,connect_timeout=8) as con:
            with con.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("""SELECT table_name FROM information_schema.tables
                    WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name""")
                table_names=[row[0] for row in cur.fetchall()]
                cur.execute("SHOW server_version")
                major=cur.fetchone()[0]
                con.rollback()
        return {"connected":True,"tables":table_names,"server_version":major}
    except Exception as exc:
        # Do not include raw psycopg exception: it can expose hostname or credentials.
        raise RuntimeError("PostgreSQL connection failed; verify private network/credentials") from None


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--sqlite",required=True,type=Path)
    args=parser.parse_args()
    result={"sqlite":inspect_sqlite(args.sqlite),
            "postgres":inspect_postgres(os.environ.get("DATABASE_URL")),
            "wrote_any_data":False}
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":main()
