"""Phase 17 fix (external review round 2, 2026-09-28) -- the script that originally
produced `human_eval_scored_results.json` was never committed (a real reproducibility
gap). This is that script, committed, plus a full, VERIFIED correction of the packet key.

ROOT CAUSE FOUND (external review round 2, follow-up): `human_eval_packet_key.json`'s
`string_date`/`llm_judge`/`nli` values do not belong to the items they are attached to.
This was first noticed on item 48 (both committed deterministic metrics disagreed with its
stored `string_date`), but tracing it further found the real cause: the key's
`internal_id` field for a given blind item does not match the internal_id whose ANSWER
TEXT actually produced that item. E.g. item 48's key says `internal_id:
"phase14-track-a-15"`, but `phase14-track-a-15`'s real, stored answer
("Jon hosted a dance competition...") is not even about Paris -- the blind item's real
actual answer ("Jon was not in Paris.") is `phase14-track-a-8`'s answer, verified by exact
text match. This is a SYSTEMATIC misalignment (the blind packet was shuffled for blinding,
but the key's metric values were not shuffled with the same permutation), not a handful of
independent bugs -- it affects 45 individual (item, field) values across 33 of the 60
items, confirmed by matching every blind item's exact `model_answer` text (unique across
all 60, zero collisions with the source) against `phase17/data/utility_repeats.json`,
which stores every Track A answer alongside its ORIGINAL, already-computed
`string_date`/`llm_judge`/`nli` values. This is not a reconstruction or a guess -- it is
the real, already-computed metric result for the exact answer text each blind item
actually contains, recovered by content match rather than by trusting the broken index.

`REBUILD_KEY_FROM_SOURCE = True` (below) makes this the default; the corrected key is
regenerated every run rather than hand-patched, so there is nothing left to keep in sync.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

HERE = Path(__file__).parent / "data"
BLIND = HERE / "human_eval_packet_blind.json"
KEY = HERE / "human_eval_packet_key.json"
UTILITY_REPEATS = HERE / "utility_repeats.json"
RATINGS = HERE / "human_eval_ratings.json"
PROXY = HERE / "llm_proxy_human_eval_results.json"
OUT = HERE / "human_eval_scored_results.json"

REBUILD_KEY_FROM_SOURCE = True


def _source_lookup_by_answer() -> Dict[str, dict]:
    """Every Track A answer this project has on record, keyed by its own exact answer
    text -- the authoritative source for `string_date`/`llm_judge`/`nli`, immune to any
    indexing/shuffling bug in a downstream packet-key file."""
    data = json.loads(UTILITY_REPEATS.read_text(encoding="utf-8"))
    by_answer: Dict[str, dict] = {}
    for run in data["runs"]:
        for row in run:
            by_answer.setdefault(row["answer"].strip(), row)
    return by_answer


def rebuild_key_from_source() -> Dict[str, dict]:
    """Rebuilds the packet key from the authoritative source by matching each blind item's
    exact answer text -- see module docstring for why the stored key cannot be trusted."""
    blind = json.loads(BLIND.read_text(encoding="utf-8"))
    by_answer = _source_lookup_by_answer()
    rebuilt = {}
    for i, it in enumerate(blind):
        src = by_answer[it["model_answer"].strip()]
        rebuilt[str(i)] = {
            "llm_judge": bool(src.get("llm_judge")),
            "nli": bool(src.get("nli")),
            "string_date": bool(src.get("string_date")),
            "internal_id": src["id"],
        }
    return rebuilt


def audit_key_corrections() -> List[dict]:
    """Every (item, field) the stored key got wrong, per the rebuilt-from-source key."""
    stored = json.loads(KEY.read_text(encoding="utf-8"))
    rebuilt = rebuild_key_from_source()
    diffs = []
    for i_str, rec in rebuilt.items():
        for field in ("string_date", "llm_judge", "nli"):
            if bool(stored[i_str].get(field)) != rec[field]:
                diffs.append({"item_id": int(i_str), "field": field,
                             "stored_wrong_value": stored[i_str].get(field), "corrected_value": rec[field],
                             "stored_wrong_internal_id": stored[i_str].get("internal_id"), "true_internal_id": rec["internal_id"]})
    return diffs


def _load_corrected_key() -> Dict[str, dict]:
    return rebuild_key_from_source() if REBUILD_KEY_FROM_SOURCE else json.loads(KEY.read_text(encoding="utf-8"))


def run() -> dict:
    ratings = {r["item_id"]: r["human_label"] for r in json.loads(RATINGS.read_text(encoding="utf-8"))}
    key = _load_corrected_key()
    proxy = json.loads(PROXY.read_text(encoding="utf-8")) if PROXY.exists() else None

    n = len(ratings)
    dist: Dict[str, int] = {}
    for lab in ratings.values():
        dist[lab] = dist.get(lab, 0) + 1

    strict_ok = lambda lab: lab in ("correct", "paraphrase")
    lenient_ok = lambda lab: lab in ("correct", "paraphrase", "partial")

    def rate(pred):
        k = sum(1 for lab in ratings.values() if pred(lab))
        from phase17.stats import rate_with_ci

        return rate_with_ci(k, n)

    def agreement(metric_key: str, human_pred) -> float:
        agree = sum(1 for iid, lab in ratings.items() if bool(key[str(iid)][metric_key]) == human_pred(lab))
        return round(100.0 * agree / n, 1)

    out = {
        "n": n,
        "human_label_distribution": dist,
        "human_strict_correct_rate": rate(strict_ok),
        "human_lenient_correct_rate": rate(lenient_ok),
        "agreement_pct": {
            "string_date_strict": agreement("string_date", strict_ok),
            "string_date_lenient": agreement("string_date", lenient_ok),
            "llm_judge_strict": agreement("llm_judge", strict_ok),
            "llm_judge_lenient": agreement("llm_judge", lenient_ok),
            "nli_strict": agreement("nli", strict_ok),
            "nli_lenient": agreement("nli", lenient_ok),
        },
        "key_rebuilt_from_source": REBUILD_KEY_FROM_SOURCE,
        "key_corrections_applied": audit_key_corrections(),
    }
    if proxy:
        out["proxy_agreement_note"] = "see llm_proxy_human_eval_results.json for the Gemini/phi3 exact-category agreement numbers (unaffected by this fix -- they compare category labels, not the string_date field)"
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    if REBUILD_KEY_FROM_SOURCE:
        KEY.write_text(json.dumps(key, indent=1, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    print(json.dumps({k: v for k, v in r.items() if k != "key_corrections_applied"}, indent=1))
    print("key corrections applied (item, field) pairs:", len(r["key_corrections_applied"]))
    print("DONE")
