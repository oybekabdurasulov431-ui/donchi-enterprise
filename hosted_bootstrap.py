"""Provision or explicitly rotate the DONCHI demo Super Admin.

The initial credentials are stored only in private Render environment variables.
DONCHI_ADMIN_PASSWORD_REVISION changes request an administrator reset exactly
once per database, avoiding a reset on every application restart.
"""
import os
import re
import time
from server import connection, onerow, now, uid


def bootstrap():
    username = os.environ.get("DONCHI_SUPERADMIN_LOGIN", "").strip().lower()
    hash_value = os.environ.get("DONCHI_SUPERADMIN_HASH", "").strip()
    revision = os.environ.get("DONCHI_ADMIN_PASSWORD_REVISION", "").strip()
    if not re.fullmatch(r"[a-z0-9_.-]{4,60}", username):
        raise RuntimeError("Invalid initial administrator username")
    if not re.fullmatch(r"pbkdf2_sha256\$350000\$[0-9a-f]{32}\$[0-9a-f]{64}", hash_value):
        raise RuntimeError("Invalid administrator password hash")
    if revision and not re.fullmatch(r"[a-zA-Z0-9_.-]{1,80}", revision):
        raise RuntimeError("Invalid password reset revision")

    with connection(write=True) as db:
        db.execute("CREATE TABLE IF NOT EXISTS bootstrap_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        admin = onerow(db, "SELECT id,username FROM users WHERE role='superadmin' LIMIT 1")
        marker = onerow(db, "SELECT value FROM bootstrap_meta WHERE key='admin_password_revision'")
        previous_revision = marker["value"] if marker else None

        if admin:
            if not revision or revision == previous_revision:
                print("Existing administrator preserved")
                return
            occupied = onerow(db, "SELECT id FROM users WHERE username=?", (username,))
            if occupied and occupied["id"] != admin["id"]:
                raise RuntimeError("Requested administrator username already exists")
            db.execute(
                "UPDATE users SET username=?,password_hash=?,active=1,"
                "session_version=session_version+1 WHERE id=?",
                (username, hash_value, admin["id"]),
            )
            db.execute(
                "UPDATE device_sessions SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL",
                (int(time.time()), admin["id"]),
            )
            db.execute(
                "DELETE FROM login_guards WHERE login_key IN (?,?)",
                (admin["username"], username),
            )
            db.execute(
                "INSERT INTO bootstrap_meta(key,value) VALUES('admin_password_revision',?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (revision,),
            )
            print("Administrator credentials rotated once; prior sessions invalidated")
            return

        count = onerow(db, "SELECT COUNT(*) AS n FROM users")["n"]
        if count != 0:
            raise RuntimeError("Existing users found without administrator; manual recovery required")
        db.execute(
            "INSERT INTO users(id,username,full_name,password_hash,role,store_id,active,created_at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (uid(), username, "DONCHI owner", hash_value, "superadmin", None, 1, now()),
        )
        if revision:
            db.execute(
                "INSERT INTO bootstrap_meta(key,value) VALUES('admin_password_revision',?)",
                (revision,),
            )
        print("Initial administrator configured")


if __name__ == "__main__":
    bootstrap()
