"""One-time first-run setup for an empty DONCHI database.

Uses a password hash supplied via private hosting environment configuration.
"""
import os
import re
from server import connection, onerow, now, uid

def bootstrap():
    username = os.environ.get("DONCHI_SUPERADMIN_LOGIN", "").strip()
    hash_value = os.environ.get("DONCHI_SUPERADMIN_HASH", "").strip()
    if not re.fullmatch(r"[a-z0-9_.-]{4,60}", username):
        raise RuntimeError("Invalid initial username")
    if not re.fullmatch(r"pbkdf2_sha256\$350000\$[0-9a-f]{32}\$[0-9a-f]{64}", hash_value):
        raise RuntimeError("Invalid initial password hash")

    with connection(write=True) as db:
        admin = onerow(db, "SELECT id FROM users WHERE role='superadmin' LIMIT 1")
        if admin:
            print("Existing administrator preserved")
            return
        count = onerow(db, "SELECT COUNT(*) AS n FROM users")["n"]
        if count != 0:
            raise RuntimeError("Existing users found: setup requires manual recovery")
        db.execute(
            "INSERT INTO users(id,username,full_name,password_hash,role,store_id,active,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (uid(), username, "DONCHI owner", hash_value, "superadmin", None, 1, now())
        )
    print("Initial administrator configured")

if __name__ == "__main__":
    bootstrap()
