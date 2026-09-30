"""Atomic merge-and-write for the JSON caches several Phase 17 processes share.

A plain `Path.write_text` on Windows intermittently failed with EINVAL when another process
had the same cache open (seen during external review round 4's baseline run). This merges
with whatever is on disk, writes to a temp file, and `os.replace`s it, with a short retry."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Dict


def merge_write(path: Path, entries: Dict, ensure_ascii: bool = True) -> None:
    for attempt in range(5):
        try:
            disk = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
            disk.update(entries)
            tmp = path.with_suffix(f".tmp{os.getpid()}")
            tmp.write_text(json.dumps(disk, ensure_ascii=ensure_ascii), encoding="utf-8")
            os.replace(tmp, path)
            return
        except (OSError, json.JSONDecodeError):
            if attempt == 4:
                raise
            time.sleep(0.5 * (attempt + 1))
