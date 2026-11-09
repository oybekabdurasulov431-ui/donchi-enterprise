"""Safe SQLite backup and offline restore verification for DONCHI.

Does not touch the live database except through a read-only connection.
Restore is intentionally create-only: NEVER overwrites an existing path.
Stdlib only, usable on Windows and Linux.
"""
from __future__ import annotations
from contextlib import closing

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
from urllib.parse import quote


def _readonly_connect(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(f"SQLite file does not exist: {path}")
    # mode=ro refuses to create a new DB. Escape special characters in paths.
    uri = "file:" + quote(path.resolve().as_posix(), safe="/:") + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=20)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def verify(path: Path) -> dict:
    """Verify structural and foreign-key consistency without changing bytes."""
    path = Path(path)
    with closing(_readonly_connect(path)) as db:
        integrity = db.execute("PRAGMA integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            raise ValueError("SQLite integrity check failed")
        # FK checks are needed even when PRAGMA integrity_check returns 'ok'.
        if db.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("SQLite foreign key violation found")
        tables = [row[0] for row in db.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )]
        schema = "\n".join(row[0] for row in db.execute(
            "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name"
        ) if row[0])
    return {
        "integrity": "ok",
        "foreign_keys": "ok",
        "table_count": len(tables),
        "schema_sha256": hashlib.sha256(schema.encode("utf-8")).hexdigest(),
        "bytes": path.stat().st_size,
    }


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _publish_new_file(temp_path: Path, destination: Path) -> None:
    """Hard-link a finished file into place atomically; never replace a path."""
    # Same directory temp files ensure hard-linking is within one filesystem.
    try:
        os.link(temp_path, destination)
    except FileExistsError:
        raise FileExistsError(f"Refusing to overwrite existing file: {destination}")
    except OSError as error:
        # Conservative: do not fall back to copy/replace, which could leave a
        # partially written backup or overwrite another process' result.
        raise OSError("Atomic create-only publish is unsupported here") from error


def backup(source: Path, destination: Path) -> dict:
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination:
        raise ValueError("Source and destination cannot match")
    if not destination.parent.is_dir():
        raise FileNotFoundError("Backup destination directory does not exist")
    if destination.exists() or destination.with_suffix(destination.suffix + ".sha256").exists():
        raise FileExistsError("Backup destination or checksum already exists")

    # A backup from a malformed source is a liability; do not create it.
    before = verify(source)
    fd, temp = tempfile.mkstemp(prefix=".donchi-snapshot-", suffix=".sqlite3", dir=destination.parent)
    temp_path = Path(temp)
    published = False
    try:
        os.fchmod(fd, 0o600) if hasattr(os, "fchmod") else None
        os.close(fd)
        with closing(_readonly_connect(source)) as src, closing(sqlite3.connect(temp_path)) as dst:
            src.backup(dst, pages=128, sleep=0.05)
        after = verify(temp_path)
        if before["schema_sha256"] != after["schema_sha256"]:
            raise ValueError("Backup schema mismatch")
        digest = sha256_file(temp_path)
        # Publish checksum sidecar only AFTER the completed DB is published.
        _publish_new_file(temp_path, destination)
        published = True
        checksum = destination.with_suffix(destination.suffix + ".sha256")
        try:
            with checksum.open("x", encoding="ascii") as file:
                file.write(digest + "\n")
                file.flush()
                os.fsync(file.fileno())
        except Exception:
            # If sidecar writing fails, fail closed: do not leave an unverified
            # published snapshot.
            destination.unlink(missing_ok=True)
            raise
        return {"sha256": digest, **after}
    finally:
        temp_path.unlink(missing_ok=True)
        if not published:
            destination.unlink(missing_ok=True) if not destination.exists() else None


def restore_to_new_path(archive: Path, target: Path) -> dict:
    """Offline restore into a NEW path. Never targets a running/live DB."""
    archive, target = Path(archive).resolve(), Path(target).resolve()
    if archive == target or target.exists():
        raise FileExistsError("Restore destination must be a new, unused file path")
    if not target.parent.is_dir():
        raise FileNotFoundError("Restore directory does not exist")
    sidecar = archive.with_suffix(archive.suffix + ".sha256")
    if not sidecar.is_file():
        raise FileNotFoundError("Expected .sha256 checksum next to backup")
    expected = sidecar.read_text(encoding="ascii").strip()
    if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
        raise ValueError("Invalid backup checksum")
    if sha256_file(archive) != expected:
        raise ValueError("Backup checksum mismatch: no files were restored")
    info = verify(archive)
    fd, temp = tempfile.mkstemp(prefix=".donchi-restore-", suffix=".sqlite3", dir=target.parent)
    temp_path = Path(temp)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as out, archive.open("rb") as inp:
            shutil.copyfileobj(inp, out, length=1024 * 1024)
            out.flush()
            os.fsync(out.fileno())
        if sha256_file(temp_path) != expected or verify(temp_path)["schema_sha256"] != info["schema_sha256"]:
            raise ValueError("Restored image did not match the backup")
        _publish_new_file(temp_path, target)
        return info
    finally:
        temp_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="DONCHI SQLite safe offline backup / restore")
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("backup")
    b.add_argument("--source", required=True, type=Path)
    b.add_argument("--output", required=True, type=Path)
    v = sub.add_parser("verify")
    v.add_argument("--source", required=True, type=Path)
    r = sub.add_parser("restore-test")
    r.add_argument("--source", required=True, type=Path)
    r.add_argument("--new-target", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "backup":
        result = backup(args.source, args.output)
    elif args.command == "verify":
        result = verify(args.source)
    else:
        result = restore_to_new_path(args.source, args.new_target)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
