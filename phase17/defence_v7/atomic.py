"""Crash-safe checkpoints for v7 runs. Importing this module makes every Path.write_text / write_bytes in the process
atomic: the content goes to a temporary file in the same folder, which then replaces the target (os.replace). A shutdown
or power loss mid-write leaves either the previous checkpoint or the new one, never a truncated file.

Every v7 entry point imports it first, so the checkpoints written by the reused v6 code (voa partials, chain partials,
Mem0 stage files, caches) are atomic too. The written content is unchanged.
"""
from __future__ import annotations

import os
import pathlib
import tempfile

_orig_text = pathlib.Path.write_text
_orig_bytes = pathlib.Path.write_bytes


def _atomic(path: pathlib.Path, writer):
    path = pathlib.Path(path)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    os.close(fd)
    try:
        n = writer(pathlib.Path(tmp))
        for attempt in range(20):                      # Windows: the target may be briefly open in another reader
            try:
                os.replace(tmp, path)
                break
            except PermissionError:
                if attempt == 19:
                    raise
                import time
                time.sleep(0.25)
        return n
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _write_text(self, data, encoding=None, errors=None, newline=None):
    return _atomic(self, lambda p: _orig_text(p, data, encoding=encoding, errors=errors, newline=newline))


def _write_bytes(self, data):
    return _atomic(self, lambda p: _orig_bytes(p, data))


if not getattr(pathlib.Path, "_v7_atomic", False):
    pathlib.Path.write_text = _write_text
    pathlib.Path.write_bytes = _write_bytes
    pathlib.Path._v7_atomic = True
