"""Tamper-evident provenance ledger (v7 engineering addition; SA7_PREREGISTRATION.md addendum C).

The v6 ledger (`defence_v6/ledger.py`) is append-only by convention: nothing stops an edit, a deletion or a reordering of
its JSONL lines, and nothing detects one. `ChainedLedger` keeps the v6 record format and API (it subclasses `Ledger`)
and adds, to every appended record:

  seq   0, 1, 2, ...
  prev  the previous record's `hash` ("0"*64 for the first)
  hash  SHA-256 (or HMAC-SHA-256 when a key is given) over the canonical JSON of the record without `hash`

and keeps a HEAD file (`<ledger>.head`: last seq and hash), written atomically. `verify()` then detects:

  edited     a record's content no longer matches its hash
  reordered  / deleted   a record's `prev` does not match its predecessor, or `seq` is not consecutive
  truncated  the last record is not the HEAD (tail entries removed)
  malformed  a line that is not JSON

With a key, the chain is also unforgeable by anyone without the key (application-level signing: it proves which
process wrote the entry, not which human). Without a key it is tamper-evident, not tamper-proof: an attacker able to
rewrite the whole file and the HEAD can recompute the chain. Both properties are stated as such.

`RewriteLog` records memory rewrites (parent digest -> child digest) on the same chain (condition C2L).
"""
from __future__ import annotations

from phase17.defence_v7 import atomic  # noqa: F401  (crash-safe checkpoints: atomic file writes)

import hashlib
import hmac
import json
import time
from pathlib import Path
from typing import Dict, List, Optional

from phase17.defence_v6.ledger import Ledger, sha

GENESIS = "0" * 64


def _canon(r: Dict) -> bytes:
    return json.dumps({k: v for k, v in r.items() if k != "hash"}, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def _digest(r: Dict, key: Optional[bytes]) -> str:
    b = _canon(r)
    return hmac.new(key, b, hashlib.sha256).hexdigest() if key else hashlib.sha256(b).hexdigest()


class ChainedLedger(Ledger):
    def __init__(self, path: Optional[Path] = None, key: Optional[bytes] = None):
        self.key = key
        self._seq, self._last = 0, GENESIS
        super().__init__(path)
        if self.path and self.path.exists():
            lines = [l for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()]
            if lines:
                last = json.loads(lines[-1])
                self._seq, self._last = last["seq"] + 1, last["hash"]

    @property
    def head_path(self) -> Optional[Path]:
        return self.path.with_name(self.path.name + ".head") if self.path else None

    def _append(self, r: Dict) -> None:
        r["seq"], r["prev"] = self._seq, self._last
        r["hash"] = _digest(r, self.key)
        self._seq, self._last = self._seq + 1, r["hash"]
        if self.path:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            self.head_path.write_text(json.dumps({"seq": r["seq"], "hash": r["hash"]}), encoding="utf-8")


def verify(path: Path, key: Optional[bytes] = None) -> Dict:
    """Check the whole chain and the HEAD. Returns {'ok', 'n', 'first_bad', 'reason'}."""
    path = Path(path)
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()] if path.exists() else []
    prev, n = GENESIS, 0
    for i, line in enumerate(lines):
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            return {"ok": False, "n": len(lines), "first_bad": i, "reason": "malformed"}
        if _digest(r, key) != r.get("hash"):
            return {"ok": False, "n": len(lines), "first_bad": i, "reason": "edited"}
        if r.get("seq") != i or r.get("prev") != prev:
            return {"ok": False, "n": len(lines), "first_bad": i, "reason": "deleted_or_reordered"}
        prev, n = r["hash"], n + 1
    head = path.with_name(path.name + ".head")
    if head.exists():
        h = json.loads(head.read_text(encoding="utf-8"))
        if h.get("hash") != prev or h.get("seq") != n - 1:
            return {"ok": False, "n": n, "first_bad": n, "reason": "truncated"}
    elif lines:
        return {"ok": False, "n": n, "first_bad": n, "reason": "head_missing"}
    return {"ok": True, "n": n, "first_bad": None, "reason": None}


class RewriteLog(ChainedLedger):
    """Rewrite events on a hash chain: the digest of the text before a rewrite -> the digest after."""

    def __init__(self, path: Optional[Path] = None, key: Optional[bytes] = None):
        self._mem: Dict[str, str] = {}
        super().__init__(path, key)

    def rewrite(self, parent_text: str, child_text: str, memory_id: Optional[str] = None) -> None:
        p, c = sha(parent_text), sha(child_text)
        self._mem[c] = p
        self._append({"rec": "rewrite", "memory_id": memory_id, "parent": p, "child": c, "ts": time.time()})

    def parents(self) -> Dict[str, str]:
        """child digest -> parent digest; read back from the file when there is one (so the verified chain is what
        is used), from memory otherwise."""
        if not (self.path and self.path.exists()):
            return dict(self._mem)
        out = {}
        for line in self.path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r.get("rec") == "rewrite":
                out[r["child"]] = r["parent"]
        return out
