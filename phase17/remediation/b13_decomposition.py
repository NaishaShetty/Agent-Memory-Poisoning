"""What B13's result depends on: channel trust, content rules, and owner-conversation corroboration
(review issues M2 / P0-4; Gap 1, provenance and governance).

FACTS FROM THE CODE (`phase17/b13_live.py`), verified by the tests in
`phase17/tests/test_remediation.py`:
  * A memory whose recorded source is `user_turn` is NEVER excluded (a hard hit downgrades to
    ALLOW_WITH_RESTRICTION) and is never corroboration-checked. Any poison that reaches the store on the
    user channel -- e.g. MINJA's query-only threat model, or a mislabelled source -- has 0% B13 exclusion
    by construction.
  * The channel label by itself excludes nothing. On untrusted channels B13 excludes when any of five rules
    fires: `base` (the Phase 6/14 grouped risk gate), `content` (B12's stacked detector), `lineage` and
    `worm` (LLM judge tiers, cached by text hash), `corroboration` (NLI support of a personal claim against
    the owner's conversation below a dev-frozen threshold).
  * Every evaluation in this project assigned attacks the `tool_output` channel (eval_round6.py:94,
    eval_round7_holdouts._decide default). The channel label is therefore an evaluator-supplied assumption.

WHAT IS COMPUTED. Per-item rule firings are read from the caches the original evaluations wrote (hold-out 4
`comp:h4:*`, hold-out 8 `h8:comp:*`, development `dev_round7_partial.json`) and, for hold-out 7 (never
cached), recomputed with the identical function and asserted to reproduce the stored B13 decisions item for
item. No threshold, rule or corpus is changed. Arms, all on the untrusted channel unless stated:

  B12_stored               the stored B12 decisions (content-only configuration)
  channel_plus_rules       base | content | lineage | worm   (B13 without corroboration)
  corroboration_only       corroboration alone
  B13                      any rule (asserted == stored B13)
  user_channel_poisoning   attacks re-labelled `user_turn`: exclusion 0 by construction; the share that
                           would be FLAGGED (restricted, still admitted) is reported
  channel_only_exclude_untrusted   exclude every untrusted memory: recall 100%, untrusted-benign FPR 100%

Paired exact McNemar tests isolate corroboration's increment (B13 vs channel_plus_rules) on attacks, with
its false-positive increment on benign. This is a post-hoc decomposition of frozen decisions, labelled as such.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

DATA = Path(__file__).resolve().parents[1] / "data"
OUT = DATA / "remediation" / "b13_decomposition.json"
PARTIAL = DATA / "remediation" / "b13_decomposition_partial.json"
RULES = ("base", "content", "lineage", "worm", "corroboration")


def _load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def _ho7_components():
    """Hold-out 7 never cached rule firings; compute them with the identical call eval_holdout8 used."""
    from phase17.b20_live import b13_components
    from phase17.holdout7_corpus import attack_records, benign_texts, verify_frozen
    from phase17.provenance_sets import owner_turns

    assert verify_frozen(), "hold-out 7 does not match its frozen digest"
    done = json.loads(PARTIAL.read_text(encoding="utf-8")) if PARTIAL.exists() else {}
    turns = owner_turns(8)
    ev, names = [t["text"] for t in turns], sorted({t["speaker"] for t in turns})
    out = {}
    for kind, texts in (("atk", [r.text for r in attack_records()]), ("ben", benign_texts())):
        k = f"h7:comp:{kind}"
        if k not in done:
            items = [(f"H7{kind}{i}", t) for i, t in enumerate(texts)]
            got = {}
            for i in range(0, len(items), 20):
                ch = items[i:i + 20]
                got.update(b13_components(ch, sources={m: "tool_output" for m, _ in ch}, evidence=ev,
                                          evidence_names=names))
            done[k] = [got[m] for m, _ in items]
            PARTIAL.parent.mkdir(parents=True, exist_ok=True)
            PARTIAL.write_text(json.dumps(done), encoding="utf-8")
        out[kind] = done[k]
    return out


def _arms(comps: List[Dict]) -> Dict[str, List[bool]]:
    from phase17.b20_live import b13_excluded_from_components

    return {
        "channel_plus_rules": [any(c[k] for k in ("base", "content", "lineage", "worm")) for c in comps],
        "corroboration_only": [bool(c["corroboration"]) for c in comps],
        "B13": [b13_excluded_from_components(c) for c in comps],
        "content_rule_only": [bool(c["content"]) for c in comps],
        # attacks relabelled to the trusted channel: never excluded; restricted iff a hard rule fires
        "user_channel_flagged_not_excluded": [any(c[k] for k in ("base", "content", "lineage", "worm")) for c in comps],
    }


def _summ(name: str, ca: List[Dict], cb: List[Dict], b13a_stored, b13b_stored, b12a, b12b) -> Dict:
    from phase17.stats import exact_mcnemar_p, rate_with_ci

    A, B = _arms(ca), _arms(cb)
    assert A["B13"] == [bool(x) for x in b13a_stored], f"{name}: components do not reproduce stored B13 (attacks)"
    assert B["B13"] == [bool(x) for x in b13b_stored], f"{name}: components do not reproduce stored B13 (benign)"
    n, nb = len(ca), len(cb)
    r = lambda v, m: rate_with_ci(sum(bool(x) for x in v), m)  # noqa: E731
    out = {"n_attacks": n, "n_benign_untrusted": nb, "reproduces_stored_B13": True, "arms": {}}
    for k in ("channel_plus_rules", "corroboration_only", "content_rule_only", "B13"):
        out["arms"][k] = {"recall": r(A[k], n), "benign_fpr_untrusted": r(B[k], nb)}
    out["arms"]["B12_stored"] = {"recall": r(b12a, n), "benign_fpr_untrusted": r(b12b, nb)}
    out["arms"]["user_channel_poisoning"] = {
        "excluded": rate_with_ci(0, n),
        "flagged_but_admitted": r(A["user_channel_flagged_not_excluded"], n),
        "note": "b13_live: trusted (user_turn) memories are never excluded and never corroboration-checked"}
    out["arms"]["channel_only_exclude_untrusted"] = {"recall": rate_with_ci(n, n), "benign_fpr_untrusted": rate_with_ci(nb, nb)}
    only_b13 = sum(a and not b for a, b in zip(A["B13"], A["channel_plus_rules"]))
    out["corroboration_increment"] = {
        "attacks_caught_only_with_corroboration": only_b13,
        "attacks_lost": 0,
        "p_exact": exact_mcnemar_p(only_b13, 0),
        "benign_fp_added": sum(a and not b for a, b in zip(B["B13"], B["channel_plus_rules"])),
        "share_of_B13_recall_from_corroboration_alone": round(only_b13 / max(1, sum(A["B13"])), 3)}
    b12 = [bool(x) for x in b12a]
    out["B13_vs_B12"] = {"only_B13": sum(a and not b for a, b in zip(A["B13"], b12)),
                         "only_B12": sum(b and not a for a, b in zip(A["B13"], b12)),
                         "p_exact": exact_mcnemar_p(sum(a and not b for a, b in zip(A["B13"], b12)),
                                                    sum(b and not a for a, b in zip(A["B13"], b12)))}
    # rule firing shares on attacks
    out["rule_firing_attacks"] = {k: r([c[k] for c in ca], n) for k in RULES}
    out["rule_firing_benign"] = {k: r([c[k] for c in cb], nb) for k in RULES}
    return out


def run() -> Dict:
    res = {"issue": "M2 / P0-4 (independent review 2026-10-12); Gap 1",
           "kind": "post-hoc decomposition of frozen per-item decisions; no parameter changed",
           "holdouts": {}}
    p4 = _load("eval_round7_holdouts_partial.json")
    e4 = _load("eval_round7_holdouts.json")["holdouts"]["holdout4"]["raw"]
    res["holdouts"]["holdout4"] = _summ("HO4", p4["comp:h4:atk"], p4["comp:h4:ben"], e4["attack"]["B13"],
                                       e4["benign"]["B13"], e4["attack"]["B12"], e4["benign"]["B12"])
    p8 = _load("eval_holdout8_partial.json")
    e8 = _load("eval_holdout8.json")["raw"]
    res["holdouts"]["holdout8"] = _summ("HO8", p8["h8:comp:atk"], p8["h8:comp:ben"], e8["attack"]["B13"],
                                       e8["benign"]["B13"], e8["attack"]["B12"], e8["benign"]["B12"])
    c7 = _ho7_components()
    e7 = _load("eval_round7b_holdouts.json")["holdouts"]["holdout7"]["raw"]
    res["holdouts"]["holdout7"] = _summ("HO7", c7["atk"], c7["ben"], e7["attack"]["B13"], e7["benign"]["B13"],
                                       e7["attack"]["B12"], e7["benign"]["B12"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    return res


if __name__ == "__main__":
    r = run()
    for h, v in r["holdouts"].items():
        a = v["arms"]
        print(h, {k: (a[k]["recall"]["k"], a[k]["benign_fpr_untrusted"]["k"]) for k in
                  ("B12_stored", "content_rule_only", "channel_plus_rules", "corroboration_only", "B13")},
              "| user-channel flagged", a["user_channel_poisoning"]["flagged_but_admitted"]["k"],
              "| corroboration increment", v["corroboration_increment"])
