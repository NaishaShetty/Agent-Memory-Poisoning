"""PL: append-only provenance ledger (v6 pre-registration §2). Standard library only (runs in mem0venv too).

One SOURCE EVENT per add: event_id, application-recorded channel (user / document / None = not recorded), principal
(an UNVERIFIED label), timestamp, sha256 of the original text, the original text, and its parsed conditional structure.
One LINK per memory event returned by the store: memory_id, store event (ADD/UPDATE/...), event_id, sha256 of the memory
text at write. A memory's sources are the UNION of every event ever linked to it (no last-writer-wins).

Nothing here is authenticated: channel and principal are whatever the application's transport code recorded.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

_COND = re.compile(r"^\s*(whenever|if|when|once|any time|anytime|in case|every time)\b\s*(?P<cond>.+?),\s*(?P<act>.+)$",
                   re.I | re.S)
_COND_MID = re.compile(r"^(?P<act>.+?)\s+\b(whenever|if|when|once|any time|anytime|every time)\b\s+(?P<cond>.+)$",
                       re.I | re.S)


def sha(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def parse_conditional(text: str) -> Optional[Dict[str, str]]:
    """Deterministic split of a rule into condition and action; None if not conditional."""
    m = _COND.match(text or "")
    if m:
        return {"condition": m.group("cond").strip(), "action": m.group("act").strip(), "form": "leading"}
    m = _COND_MID.match(text or "")
    if m:
        return {"condition": m.group("cond").strip(), "action": m.group("act").strip(), "form": "trailing"}
    return None


class Ledger:
    """In-memory view backed by an append-only JSONL file (or memory only when path is None)."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else None
        self.events: Dict[str, Dict] = {}
        self.links: List[Dict] = []
        if self.path and self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                r = json.loads(line)
                (self.events.__setitem__(r["event_id"], r) if r["rec"] == "event" else self.links.append(r))

    def _append(self, r: Dict) -> None:
        if self.path:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def record_event(self, text: str, channel: Optional[str], principal: Optional[str] = None,
                     claims: Optional[List[str]] = None) -> str:
        eid = str(uuid.uuid4())
        claims = claims or [text]
        r = {"rec": "event", "event_id": eid, "channel": channel, "principal": principal, "principal_authenticated": False,
             "ts": time.time(), "sha256": sha(text), "text": text, "claims": claims,
             "conditional": [parse_conditional(c) for c in claims]}
        self.events[eid] = r
        self._append(r)
        return eid

    def link(self, memory_id: str, store_event: str, event_id: str, memory_text: str) -> None:
        r = {"rec": "link", "memory_id": memory_id, "store_event": store_event, "event_id": event_id,
             "mem_sha256": sha(memory_text), "mem_text": memory_text, "ts": time.time()}
        self.links.append(r)
        self._append(r)

    def sources(self, memory_id: str) -> List[Dict]:
        """Union of linked events (missing events are returned as {'event_id', 'missing': True})."""
        out, seen = [], set()
        for l in self.links:
            if l["memory_id"] == memory_id and l["event_id"] not in seen:
                seen.add(l["event_id"])
                out.append(self.events.get(l["event_id"], {"event_id": l["event_id"], "missing": True}))
        return out

    def channels(self, memory_id: str) -> List[Optional[str]]:
        return [s.get("channel") if not s.get("missing") else "MISSING_EVENT" for s in self.sources(memory_id)]

    def untrusted(self, memory_id: str) -> bool:
        """True unless every linked source is a recorded USER channel event. No sources -> untrusted (fail-safe)."""
        ch = self.channels(memory_id)
        return (not ch) or any(c != "user" for c in ch)
