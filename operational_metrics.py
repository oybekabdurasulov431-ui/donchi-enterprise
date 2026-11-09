"""Process-local, bounded and privacy-preserving API diagnostics.

Only aggregate statuses and timings are kept, with a short rolling list of
server errors. No headers, URL parameters, request bodies or user identifiers.
Counters reset when the Render container restarts; this is not external APM.
"""
from __future__ import annotations
from collections import Counter, deque
from datetime import datetime, timezone
from threading import Lock
import time

_LOCK = Lock()
STARTED = time.monotonic()
COUNT = Counter()
ERRORS = deque(maxlen=40)
SLOW = deque(maxlen=40)
TOTAL_DURATION_MS = 0.0
MAX_DURATION_MS = 0.0


def record(method: str, status: int, elapsed_ms: float, request_id: str) -> None:
    global TOTAL_DURATION_MS, MAX_DURATION_MS
    if not isinstance(status, int) or status < 100 or status > 599:
        return
    status_family = f"{status // 100}xx"
    duration = max(0., round(float(elapsed_ms), 2))
    # Labels do not contain route strings, user info, URL, query parameters.
    with _LOCK:
        COUNT[status_family] += 1
        COUNT["total"] += 1
        TOTAL_DURATION_MS += duration
        MAX_DURATION_MS = max(MAX_DURATION_MS, duration)
        if status >= 500:
            ERRORS.append({
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "method": method if method in ("GET","POST","PUT","PATCH","DELETE") else "OTHER",
                "status": status,
                "request_id": request_id,
            })
        if duration >= 2000.0:
            SLOW.append({
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "duration_ms": duration,
                "status": status,
                "request_id": request_id,
            })


def snapshot() -> dict:
    with _LOCK:
        count = dict(COUNT)
        errors = list(reversed(ERRORS))
        slow = list(reversed(SLOW))
        total = count.get("total", 0)
        average = round(TOTAL_DURATION_MS / total, 2) if total else 0.
        max_latency = MAX_DURATION_MS
    return {
        "source": "process_memory",
        "note": "Only current process. Counters reset at restart; not persistent monitoring.",
        "uptime_seconds": int(time.monotonic() - STARTED),
        "request_counts": count,
        "average_latency_ms": average,
        "max_latency_ms": max_latency,
        "recent_server_errors": errors,
        "recent_slow_requests": slow,
    }
