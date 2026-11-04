#!/usr/bin/env sh
set -e
cd "$(dirname "$0")"
python3 -m pip install -r requirements.txt
printf '\nDONCHI Super Admin: http://127.0.0.1:8787/platform/\nDo\047kon Admin: http://127.0.0.1:8787/app/\n\n'
python3 setup_admin.py || exit 1
python3 -m uvicorn server:app --host 127.0.0.1 --port 8787
