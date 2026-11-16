"""Fail closed before writing business data to an ephemeral Railway filesystem."""
from __future__ import annotations

import os
from pathlib import Path


def is_mounted_volume(path: Path, mountinfo: str | None = None) -> bool:
    """Check that the configured data directory itself is a mounted volume."""
    # Supplied mountinfo is a Linux fixture even when tests run on Windows.
    fixture = mountinfo is not None
    if mountinfo is None:
        mountinfo = Path('/proc/self/mountinfo').read_text(encoding='utf-8')
    target = path.as_posix() if fixture and path.as_posix().startswith('/') else str(path.resolve())
    for line in mountinfo.splitlines():
        fields = line.split()
        if len(fields) > 4 and fields[4].replace('\\040', ' ') == target:
            return True
    return False


def require_persistent_storage(data_dir: Path, environ: dict | None = None,
                               mountinfo: str | None = None) -> None:
    env = os.environ if environ is None else environ
    if not (env.get('RAILWAY_ENVIRONMENT_ID') or env.get('RAILWAY_PROJECT_ID')):
        return
    if not env.get('DONCHI_DATA_DIR'):
        raise RuntimeError('DONCHI STORAGE BLOCKED: Set DONCHI_DATA_DIR to the Railway app volume mount (for example /data). Database was NOT initialized.')
    # A synthetic Linux mountinfo test contains /data, but Windows Path('/data')
    # does not report is_absolute(). Runtime checks still require real absolute paths.
    absolute = data_dir.is_absolute() or (mountinfo is not None and data_dir.as_posix().startswith('/'))
    if not absolute or not is_mounted_volume(data_dir, mountinfo):
        raise RuntimeError('DONCHI STORAGE BLOCKED: DONCHI_DATA_DIR must be the exact mounted Railway app volume directory. Database was NOT initialized.')
