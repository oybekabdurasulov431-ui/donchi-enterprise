"""Safely snapshot the existing DONCHI SQLite DB before any PostgreSQL cutover.

RUN ONLY from an environment with access to the real live SQLite file.
No server routes, no implicit uploads and no modification of the source DB.
Example:
  python scripts/backup_sqlite_before_migration.py --db /app/data/yempro.sqlite3 --out /secure-backup
Keep the generated files in an access-controlled, off-server backup location.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def snapshot(source: Path, output_dir: Path) -> dict:
    source=source.resolve(strict=True)
    if not source.is_file():raise ValueError("SQLite source must be a file")
    output_dir.mkdir(parents=True, exist_ok=True)
    if output_dir.resolve()==source.parent:
        raise ValueError("Save backups outside the live SQLite directory")
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target=output_dir/("donchi-sqlite-"+stamp+".sqlite3")
    if target.exists():raise FileExistsError("Backup already exists: "+str(target))
    with sqlite3.connect("file:"+source.as_posix()+"?mode=ro",uri=True) as src:
        if src.execute("PRAGMA quick_check(1)").fetchone()[0]!="ok":
            raise RuntimeError("Source database failed SQLite integrity check")
        with sqlite3.connect(str(target)) as dst:
            src.backup(dst)
    try:
        with sqlite3.connect(str(target)) as db:
            if db.execute("PRAGMA quick_check(1)").fetchone()[0]!="ok":
                raise RuntimeError("Backup integrity check failed")
            tables=[str(row[0]) for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
            row_counts={name:db.execute('SELECT COUNT(*) FROM "'+name.replace('"','""')+'"').fetchone()[0] for name in tables}
        digest=hashlib.sha256(target.read_bytes()).hexdigest()
        record={"format":"donchi-sqlite-backup-v1","created_at":datetime.now(timezone.utc).isoformat(),
                "file":target.name,"size_bytes":target.stat().st_size,"sha256":digest,
                "tables":row_counts}
        manifest=target.with_suffix(".manifest.json")
        with manifest.open("x",encoding="utf-8") as f:
            json.dump(record,f,ensure_ascii=False,indent=2)
        try:
            os.chmod(target,0o600);os.chmod(manifest,0o600)
        except OSError:pass
        return {"database_file":str(target),"manifest_file":str(manifest),"sha256":digest,
                "table_count":len(tables),"total_rows":sum(row_counts.values())}
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def main():
    parser=argparse.ArgumentParser(description="Create a consistent DONCHI SQLite backup")
    parser.add_argument("--db",required=True,type=Path,help="Existing SQLite file")
    parser.add_argument("--out",required=True,type=Path,help="Separate, protected backup directory")
    args=parser.parse_args()
    print(json.dumps(snapshot(args.db,args.out),ensure_ascii=False,indent=2))


if __name__=="__main__":main()
