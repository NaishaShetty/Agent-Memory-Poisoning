"""The ONE scoring of hold-outs 6 and 7 (round 7, items 6 and 10).

Same discipline as `eval_round7_holdouts`: refuses to run unless the pre-registration addendum for
these two corpora is complete (no PENDING), records both frozen digests, and is committed; both
corpora are digest-checked. Nothing is fitted here.

  hold-out 6 (SPML injection, matched benign, no evidence): B12-B15, B17, B18 and the published
    baselines; agent compliance raw and framed on every attack, so the neutralisation policies are
    computed for every detector; and the without-memory arm, so its causal working subset comes from
    the same run.
  hold-out 7 (base-model-authored memory poisoning, owner LoCoMo 8, with evidence): the same
    configurations plus B13c = B13 OR (a personal claim the owner's conversation CONTRADICTS at the
    frozen dev threshold, `corroboration_v2.TAU_CONTR`) -- item 3's clean test; benign on the
    untrusted and user_turn channels; framed-arm compliance from `holdout7_validity`.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Dict

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(__file__).parent / "data"
OUT = DATA / "eval_round7b_holdouts.json"
PARTIAL = DATA / "eval_round7b_holdouts_partial.json"
PREREG = ROOT / "docs" / "phase17" / "PREREGISTRATION_ROUND7.md"
MARK = "## Addendum 3"


def preregistration_in_force() -> None:
    from phase17 import holdout6_corpus as h6, holdout7_corpus as h7

    txt = PREREG.read_text(encoding="utf-8")
    if MARK not in txt:
        raise SystemExit("the pre-registration addendum for hold-outs 6 and 7 has not been written")
    block = txt.split(MARK, 1)[1]
    if "PENDING" in block:
        raise SystemExit("the hold-out 6/7 addendum still has PENDING sections")
    for h in (h6, h7):
        assert h.verify_frozen(), f"{h.__name__} does not match its frozen digest"
        if json.loads(h.FREEZE.read_text(encoding="utf-8"))["sha256"] not in block:
            raise SystemExit(f"the addendum does not record {h.__name__}'s digest")
    dirty = subprocess.run(["git", "status", "--porcelain", str(PREREG)], cwd=str(ROOT),
                           capture_output=True, text=True).stdout.strip()
    if dirty:
        raise SystemExit("commit the completed addendum before scoring either hold-out")


def _contradicted(texts, evidence, names, done, key):
    """Item 3's frozen rule on each text: a personal claim with max contradiction >= TAU_CONTR."""
    from phase17.b13_live import is_personal_claim
    from phase17.corroboration_v2 import FIT, profile

    tau = json.loads(FIT.read_text(encoding="utf-8"))["TAU_CONTR"]
    if key not in done:
        ix = [i for i, t in enumerate(texts) if is_personal_claim(t, names)]
        prof = profile([texts[i] for i in ix], evidence)
        hit = {i for i, p in zip(ix, prof) if p["contr"] >= tau}
        done[key] = [i in hit for i in range(len(texts))]
        PARTIAL.write_text(json.dumps(done), encoding="utf-8")
    return done[key]


def run() -> dict:
    preregistration_in_force()
    from phase17 import eval_round7_holdouts as E, dev_round7
    from phase17.compose_neutralise import compliance, summarise
    from phase17.eval_holdout3 import _baseline_flags
    from phase17.holdout6_corpus import attack_records as h6a, benign_texts as h6b
    from phase17.holdout7_corpus import attack_records as h7a, benign_texts as h7b
    from phase17.holdout7_validity import framed_compliance, raw_compliance
    from phase17.neutralise import WINNER
    from phase17.precompute_features import run as precompute
    from phase17.provenance_sets import owner_turns
    from phase17.stats import rate_with_ci

    E.PARTIAL = PARTIAL                       # every checkpoint goes to THIS module's partial
    dev_round7.PARTIAL = PARTIAL
    done = json.loads(PARTIAL.read_text(encoding="utf-8")) if PARTIAL.exists() else {}
    a6, b6 = [r.text for r in h6a()], h6b()
    a7, b7 = [r.text for r in h7a()], h7b()
    precompute(a6 + b6 + a7 + b7)
    turns = owner_turns(8)
    ev, names = [t["text"] for t in turns], sorted({t["speaker"] for t in turns})
    out: Dict = {"preregistration": f"{PREREG.relative_to(ROOT)} ({MARK.strip('# ')})", "holdouts": {}}

    # ---------------- hold-out 6
    A = {c: E._decide(c, a6, f"H6A{c}", done, f"h6:atk:{c}") for c in E.CONFIGS}
    B = {c: E._decide(c, b6, f"H6B{c}", done, f"h6:ben:{c}") for c in E.CONFIGS}
    bla, blb = _baseline_flags(a6), _baseline_flags(b6)
    c_raw, c_neu = compliance(a6, "raw"), compliance(a6, WINNER)
    h6 = {"n_attacks": len(a6), "n_benign": len(b6), "configs": {}, "baselines": {}}
    for c in A:
        h6["configs"][c] = {"attack_recall": rate_with_ci(sum(A[c]), len(a6)),
                            "matched_benign_fpr": rate_with_ci(sum(B[c]), len(b6))}
    for k in bla:
        h6["baselines"][k] = {"attack_recall": rate_with_ci(sum(bla[k]), len(a6)),
                              "matched_benign_fpr": rate_with_ci(sum(blb[k]), len(b6))}
    dets = {c: (A[c], B[c]) for c in A}
    dets.update({k: (bla[k], blb[k]) for k in ("deberta_pi_v2@oracle", "deberta_pi_v2@dev")})
    h6["neutralisation"] = summarise(c_raw, c_neu, dets)
    h6["raw"] = {"attack": A, "benign": B, "compliance_raw": c_raw, "compliance_framed": c_neu,
                 "degree": [json.loads((DATA / "holdout6_corpus.json").read_text(encoding="utf-8"))
                            ["attacks"][i]["degree"] for i in range(len(a6))]}
    out["holdouts"]["holdout6"] = h6

    # ---------------- hold-out 7 (with the owner's conversation)
    A7 = {c: E._decide(c, a7, f"H7A{c}", done, f"h7:atk:{c}", ev, names) for c in E.CONFIGS}
    B7 = {c: E._decide(c, b7, f"H7B{c}", done, f"h7:ben:{c}", ev, names) for c in E.CONFIGS}
    B7u = {c: E._decide(c, b7, f"H7U{c}", done, f"h7:benu:{c}", ev, names, "user_turn") for c in E.CONFIGS}
    ca = _contradicted(a7, ev, names, done, "h7:atk:contr")
    cb = _contradicted(b7, ev, names, done, "h7:ben:contr")
    A7["B13c"] = [x or y for x, y in zip(A7["B13"], ca)]
    B7["B13c"] = [x or y for x, y in zip(B7["B13"], cb)]
    B7u["B13c"] = list(B7u["B13"])                 # trusted channel: corroboration never excludes
    bl7a, bl7b = _baseline_flags(a7), _baseline_flags(b7)
    c7raw, c7neu = raw_compliance(), framed_compliance()
    ids = [r.scenario_id for r in h7a()]
    h7 = {"n_attacks": len(a7), "n_benign": len(b7), "evidence": "LoCoMo sample 8 (the owner)",
          "configs": {}, "baselines": {}}
    for c in A7:
        h7["configs"][c] = {"attack_recall": rate_with_ci(sum(A7[c]), len(a7)),
                            "benign_fpr_untrusted_channel": rate_with_ci(sum(B7[c]), len(b7)),
                            "benign_fpr_user_turn": rate_with_ci(sum(B7u[c]), len(b7))}
    for k in bl7a:
        h7["baselines"][k] = {"attack_recall": rate_with_ci(sum(bl7a[k]), len(a7)),
                              "benign_fpr_untrusted_channel": rate_with_ci(sum(bl7b[k]), len(b7))}
    h7["neutralisation"] = summarise(c7raw, c7neu, {c: (A7[c], B7[c]) for c in A7})
    h7["raw"] = {"attack": A7, "benign": B7, "benign_user_turn": B7u, "compliance_raw": c7raw,
                 "compliance_framed": c7neu, "attack_ids": ids,
                 "attack_family": [r.family for r in h7a()]}
    out["holdouts"]["holdout7"] = h7
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    for h, v in r["holdouts"].items():
        print(f"\n### {h}: {v['n_attacks']} attacks / {v['n_benign']} benign")
        for c, x in v["configs"].items():
            f = x.get("matched_benign_fpr") or x.get("benign_fpr_untrusted_channel")
            print(f"  {c:5s} recall {x['attack_recall']['rate']:6.1%}  benign FPR {f['rate']:6.1%}")
    print("DONE")
