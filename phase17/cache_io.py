"""Atomic merge-and-write for the JSON caches several Phase 17 processes share.

A plain `Path.write_text` on Windows intermittently failed with EINVAL when another process
had the same cache open (seen during external review round 4's baseline run). This merges
with whatever is on disk, writes to a temp file, and `os.replace`s it, with a short retry."""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Dict

# merge_write was process-safe (the temp name carries the PID) but NOT thread-safe: several
# worker threads in ONE process shared that temp path, so thread A could os.replace a file
# thread B was still writing, leaving valid JSON followed by trailing bytes. That is exactly
# how judge_cache.json was corrupted during a 3-worker adaptive run, and the symptom --
# "Extra data: line 1 column N" surviving all five retries -- is a persistently broken file
# rather than the transient contention the retry was written for.
_LOCK = threading.Lock()


def merge_write(path: Path, entries: Dict, ensure_ascii: bool = True) -> None:
    with _LOCK:
        _merge_write_locked(path, entries, ensure_ascii)


def _merge_write_locked(path: Path, entries: Dict, ensure_ascii: bool = True) -> None:
    for attempt in range(5):
        try:
            disk = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
            disk.update(entries)
            tmp = path.with_suffix(f".tmp{os.getpid()}.{threading.get_ident()}")
            tmp.write_text(json.dumps(disk, ensure_ascii=ensure_ascii), encoding="utf-8")
            os.replace(tmp, path)
            return
        except json.JSONDecodeError:
            # A persistently malformed file is not contention; recover its valid prefix rather
            # than retrying four more times and then killing a multi-hour run.
            if attempt >= 1:
                raw = path.read_text(encoding="utf-8", errors="replace")
                try:
                    disk, _end = json.JSONDecoder().raw_decode(raw)
                except Exception:
                    disk = {}
                disk.update(entries)
                tmp = path.with_suffix(f".tmp{os.getpid()}.{threading.get_ident()}")
                tmp.write_text(json.dumps(disk, ensure_ascii=ensure_ascii), encoding="utf-8")
                os.replace(tmp, path)
                return
            time.sleep(0.5 * (attempt + 1))
        except OSError:
            if attempt == 4:
                raise
            time.sleep(0.5 * (attempt + 1))
