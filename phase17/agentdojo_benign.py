"""Benign tool-output text from AgentDojo's own environment data (MIT), as memory records.

WHY: source-aware trust needs an honest worst case — text that is genuinely benign but
arrives through an UNTRUSTED channel (a calendar entry, an email, a transaction record, a
hotel listing), rather than only benign text the user said themselves. Without it, a
"trust the user, check everything else" rule can look free when it is not.

DEDUPLICATION (external review round 5, 2026-09-30): this extract was originally produced by
an inline script that assigned dev/test by row index, and `test_review5_fixes.py` then caught
a real leak — AgentDojo's environment contains repeated entries (a weekly "yoga class"
calendar event, near-identical transactions), so the same text landed in both halves: 4 of
74 rows were duplicates and 1 text appeared on both sides of the split. Items are now
deduplicated on normalized text BEFORE the split, and the split is taken over the unique
texts in sorted order, so it is deterministic and reproducible from this module rather than
from a shell history.

Entries carrying an injection placeholder (`{...}`) are excluded: those are the slots
AgentDojo fills with its attacks, so their contents are not benign.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

OUT = Path(__file__).parent / "data" / "agentdojo_benign_tool_outputs.json"
SOURCE_NOTE = ("github.com/ethz-spylab/agentdojo (MIT), v1 suite environment data (benign tool-output "
               "text; entries carrying an injection placeholder are excluded). AgentDojo's workspace "
               "suite ships gpt_prompts.txt, i.e. some of this environment text was LLM-assisted by "
               "the AgentDojo authors -- external to this project either way.")


def _norm(t: str) -> str:
    return " ".join(t.lower().split())


def build(agentdojo_root: Path) -> dict:
    import yaml

    root = Path(agentdojo_root) / "src/agentdojo/data/suites"
    rows: List[Dict] = []

    def add(kind: str, text: str, suite: str):
        if not isinstance(text, str):
            return
        t = " ".join(text.split())
        if "{" in t or len(t) < 25:
            return
        rows.append({"kind": kind, "suite": suite, "text": t[:400]})

    ws = root / "workspace/include"
    for e in yaml.safe_load((ws / "calendar.yaml").read_text(encoding="utf-8"))["initial_events"]:
        add("calendar_event", f"Calendar event '{e['title']}': {e.get('description','')}", "workspace")
    for e in yaml.safe_load((ws / "inbox.yaml").read_text(encoding="utf-8"))["initial_emails"]:
        add("email", f"Email from {e['sender']} -- {e['subject']}: {e['body'].split(chr(10)+chr(10))[0]}", "workspace")
    bank = yaml.safe_load((root / "banking/environment.yaml").read_text(encoding="utf-8"))
    for t in bank["bank_account"].get("transactions", []) + bank["bank_account"].get("scheduled_transactions", []):
        add("transaction", f"Bank transaction: {t['amount']} to {t['recipient']} -- {t['subject']}", "banking")
    tr = yaml.safe_load((root / "travel/environment.yaml").read_text(encoding="utf-8"))
    for h in tr["hotels"]["hotel_list"]:
        add("hotel_info", f"Hotel {h['name']} in {h['city']}: rating {h['rating']}, price {h['price_min']}-"
                          f"{h['price_max']}, address {h['address']}", "travel")
    for r in tr["restaurants"]["restaurant_list"]:
        add("restaurant_info", f"Restaurant {r['name']} in {r['city']}: {r['cuisine_type']} cuisine, "
                               f"{r.get('dietary_restrictions','')}, rating {r['rating']}", "travel")

    # Deduplicate on normalized text BEFORE splitting, then split deterministically.
    seen, unique = set(), []
    for r in rows:
        k = _norm(r["text"])
        if k in seen:
            continue
        seen.add(k)
        unique.append(r)
    unique.sort(key=lambda r: r["text"])
    items = [dict(r, id=f"ADJ-BEN-{i}", split=("dev" if i % 2 == 0 else "test")) for i, r in enumerate(unique)]
    data = {"source": SOURCE_NOTE, "n_raw": len(rows), "n_unique": len(items), "items": items}
    OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    return data


def agentdojo_benign(split: str) -> List[str]:
    if not OUT.exists():
        return []
    return [i["text"] for i in json.loads(OUT.read_text(encoding="utf-8"))["items"] if i["split"] == split]


if __name__ == "__main__":
    import sys

    d = build(Path(sys.argv[1]))
    print(f"raw {d['n_raw']} -> unique {d['n_unique']}; dev {len(agentdojo_benign('dev'))} "
          f"test {len(agentdojo_benign('test'))}")
    print("DONE")
