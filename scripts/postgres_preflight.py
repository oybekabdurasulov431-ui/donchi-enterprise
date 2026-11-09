"""Read-only SQLite -> PostgreSQL migration preflight.

This does not connect to PostgreSQL, modify any database, or provision services.
It reports schema inventory, SQLite dependencies, tenant checks and a
migration readiness checklist, without outputting customer records or secrets.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import quote

EXPECTED_TENANT_TABLES = (
    "products","customers","sales","sale_items","debt_payments","movements",
    "expenses","cash_shifts","sale_returns","branches","branch_stock",
    "inventory_lots","deliveries","supplier_bills","supplier_payments",
)


def inventory(path: Path) -> dict:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError("Database not found; migration readiness cannot be checked")
    uri = "file:" + quote(path.resolve().as_posix(), safe="/:") + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as db:
        check = db.execute("PRAGMA integrity_check").fetchone()
        if not check or check[0] != "ok":
            raise ValueError("SQLite database integrity check failed")
        if db.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("SQLite foreign key violations found")
        tables = db.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        items = []
        names = {name for name,_ in tables}
        for name, definition in tables:
            # Table names originate from sqlite_master, quote them nevertheless.
            quoted = '"' + name.replace('"','""') + '"'
            columns = [row[1] for row in db.execute(f'PRAGMA table_info({quoted})')]
            rows = db.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0]
            foreign_keys = db.execute(f"PRAGMA foreign_key_list({quoted})").fetchall()
            items.append({
                "name": name,
                "row_count": rows,
                "has_store_id": "store_id" in columns,
                "foreign_key_count": len(foreign_keys),
                "column_count": len(columns),
                "sqlite_specific_types": bool(re.search(r"\bREAL\b|\bBLOB\b",definition or "",re.I)),
            })
    missing = [name for name in EXPECTED_TENANT_TABLES if name not in names]
    tenant_missing = [
        item["name"] for item in items
        if item["name"] in EXPECTED_TENANT_TABLES and not item["has_store_id"]
    ]
    return {
        "database_integrity": "ok",
        "foreign_keys": "ok",
        "tables": items,
        "missing_expected_tables": missing,
        "tenant_tables_without_store_id": tenant_missing,
        "postgresql_connected": False,
        "migration_executed": False,
        "readiness": "manual_schema_conversion_required",
        "next_steps": [
            "Provision an approved persistent PostgreSQL service (not done here)",
            "Write versioned PostgreSQL schema migrations and adapter for placeholders and transactions",
            "Review tenant relations and preserve IDs and referential integrity",
            "Create a verified SQLite snapshot and restore it to a staging PostgreSQL database",
            "Compare table counts, stock, debt and sales totals before cutover",
            "Practice rollback and schedule encrypted off-site backups",
        ],
    }


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",required=True,type=Path)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    result=inventory(args.source)
    encoded=json.dumps(result,indent=2,ensure_ascii=False)
    if args.output:
        with args.output.open("x",encoding="utf-8") as file:
            file.write(encoded+"\n")
    else:
        print(encoded)


if __name__=="__main__":
    main()
