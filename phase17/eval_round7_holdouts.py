"""The ONE scoring of hold-outs 4 and 5, for every round-7 configuration at once.

REFUSES TO RUN unless `docs/phase17/PREREGISTRATION_ROUND7.md` is complete (no PENDING section),
records both frozen digests, and is COMMITTED -- so git history shows the predictions preceding
every artifact that contains a decision on either hold-out. Both corpora are digest-checked.

  hold-out 5 (injection, toxic-chat): B12-B15, B17, B18, B20, B21 and the published baselines at
    their round-5 thresholds, on 131 attacks and 1,000 matched benign, no evidence (none exists);
    plus agent compliance raw and framed on every attack, so the neutralisation policies P0-P4
    are computed for every detector.
  hold-out 4 (memory poisoning, mistral, owner = LoCoMo sample 7): the same configurations WITH
    the owner's conversation as evidence, benign on the untrusted channel (strict) and on the
    user_turn channel; plus framed-arm compliance, with the raw arm taken from the causal validity
    audit's with-memory answers (same task, store and judge).

Every rate is reported on the full population; working-subset rates for hold-out 4 are computed
by `report_round7` from `holdout4_validity.json`, which is a corpus property and consults no
decision made here.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Dict, List, Sequence

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(__file__).parent / "data"
OUT = DATA / "eval_round7_holdouts.json"
PARTIAL = DATA / "eval_round7_holdouts_partial.json"
PREREG = ROOT / "docs" / "phase17" / "PREREGISTRATION_ROUND7.md"
CONFIGS = ("B12", "B13", "B14", "B15", "B17", "B18")
BATCH = 4


def preregistration_in_force() -> None:
    from phase17 import holdout4_corpus as h4, holdout5_corpus as h5

    txt = PREREG.read_text(encoding="utf-8")
    if "PENDING" in txt:
        raise SystemExit("the round-7 pre-registration still has PENDING sections")
    for h in (h4, h5):
        assert h.verify_frozen(), f"{h.__name__} does not match its frozen digest"
        d = json.loads(h.FREEZE.read_text(encoding="utf-8"))["sha256"]
        if d not in txt:
            raise SystemExit(f"the pre-registration does not record {h.__name__}'s digest")
    r = subprocess.run(["git", "status", "--porcelain", str(PREREG)], cwd=str(ROOT),
                       capture_output=True, text=True)
    logged = subprocess.run(["git", "log", "--oneline", "--", str(PREREG)], cwd=str(ROOT),
                            capture_output=True, text=True).stdout.strip()
    if r.stdout.strip() or not logged:
        raise SystemExit("commit the completed pre-registration before scoring either hold-out")


def _decide(cfg, texts, prefix, done, key, evidence=None, names=(), source="tool_output"):
    from phase14.defended_retrieval import apply_defense

    out = list(done.get(key, []))
    for i in range(len(out), len(texts), BATCH):
        chunk = tuple((f"{prefix}-{i+j}", t) for j, t in enumerate(texts[i:i + BATCH]))
        ctx = {}
        if cfg != "B12":
            ctx["sources"] = {m: source for m, _ in chunk}
            if evidence:
                ctx.update(evidence=evidence, evidence_names=names)
        _, dec = apply_defense(cfg, chunk, **ctx)
        out += [bool(d.excluded) for d in dec]
        if (i // BATCH) % 10 == 0:
            done[key] = out
            PARTIAL.write_text(json.dumps(done), encoding="utf-8")
            print(f"    {key} {len(out)}/{len(texts)}", flush=True)
    done[key] = out
    PARTIAL.write_text(json.dumps(done), encoding="utf-8")
    return out


def _b20_b21(texts, prefix, done, key, b14, evidence=None, names=(), source="tool_output"):
    from phase17.b20_live import b13_provenance_excluded
    from phase17.dev_round7 import _components, _deb

    comps = _components(texts, prefix, done, f"comp:{key}", evidence, names, source)
    b20 = [bool(x) or b13_provenance_excluded(c) for x, c in zip(b14, comps)]
    deb = _deb(texts)
    return b20, [a or d for a, d in zip(b20, deb)]


def _score_half(texts, prefix, done, tag, evidence=None, names=(), source="tool_output"):
    d = {c: _decide(c, texts, f"{prefix}{c}", done, f"{tag}:{c}", evidence, names, source)
         for c in CONFIGS}
    d["B20"], d["B21"] = _b20_b21(texts, prefix, done, tag, d["B14"], evidence, names, source)
    return d


def run() -> dict:
    preregistration_in_force()
    from phase17 import dev_round7
    from phase17.compose_neutralise import compliance, summarise
    from phase17.eval_holdout3 import _baseline_flags
    from phase17.holdout4_corpus import attack_records as h4a, benign_texts as h4b
    from phase17.holdout5_corpus import attack_records as h5a, benign_texts as h5b
    from phase17.neutralise import WINNER
    from phase17.precompute_features import run as precompute
    from phase17.provenance_sets import owner_turns
    from phase17.stats import rate_with_ci

    dev_round7.PARTIAL = PARTIAL            # components checkpoint into THIS module's partial
    done = json.loads(PARTIAL.read_text(encoding="utf-8")) if PARTIAL.exists() else {}
    a5, b5 = [r.text for r in h5a()], h5b()
    a4, b4 = [r.text for r in h4a()], h4b()
    precompute(a5 + b5 + a4 + b4)
    turns = owner_turns(7)
    ev, names = [t["text"] for t in turns], sorted({t["speaker"] for t in turns})

    out: Dict = {"preregistration": str(PREREG.relative_to(ROOT)), "holdouts": {}}
    # ---------------- hold-out 5
    A = _score_half(a5, "H5A", done, "h5:atk")
    B = _score_half(b5, "H5B", done, "h5:ben")
    bla, blb = _baseline_flags(a5), _baseline_flags(b5)
    c_raw, c_neu = compliance(a5, "raw"), compliance(a5, WINNER)
    h5 = {"n_attacks": len(a5), "n_benign": len(b5), "configs": {}, "baselines": {}}
    for c in A:
        h5["configs"][c] = {"attack_recall": rate_with_ci(sum(A[c]), len(a5)),
                            "matched_benign_fpr": rate_with_ci(sum(B[c]), len(b5))}
    for k in bla:
        h5["baselines"][k] = {"attack_recall": rate_with_ci(sum(bla[k]), len(a5)),
                              "matched_benign_fpr": rate_with_ci(sum(blb[k]), len(b5))}
    dets = {c: (A[c], B[c]) for c in A}
    dets.update({k: (bla[k], blb[k]) for k in ("deberta_pi_v2@oracle", "deberta_pi_v2@dev")})
    h5["neutralisation"] = summarise(c_raw, c_neu, dets)
    h5["raw"] = {"attack": A, "benign": B, "compliance_raw": c_raw, "compliance_framed": c_neu}
    out["holdouts"]["holdout5"] = h5

    # ---------------- hold-out 4 (with the owner's conversation)
    A4 = _score_half(a4, "H4A", done, "h4:atk", ev, names)
    B4 = _score_half(b4, "H4B", done, "h4:ben", ev, names)
    B4u = _score_half(b4, "H4U", done, "h4:benu", ev, names, source="user_turn")
    bl4a, bl4b = _baseline_flags(a4), _baseline_flags(b4)
    ids = [r.scenario_id for r in h4a()]
    # The raw arm is the causal audit's WITH-memory compliance (same task, store, judge); the
    # framed arm re-asks with the poison framed. Both come from holdout4_validity's caches.
    from phase17.holdout4_validity import framed_compliance, raw_compliance

    c4raw, c4neu = raw_compliance(), framed_compliance()
    h4 = {"n_attacks": len(a4), "n_benign": len(b4), "evidence": "LoCoMo sample 7 (the owner)",
          "configs": {}, "baselines": {}}
    for c in A4:
        h4["configs"][c] = {"attack_recall": rate_with_ci(sum(A4[c]), len(a4)),
                            "benign_fpr_untrusted_channel": rate_with_ci(sum(B4[c]), len(b4)),
                            "benign_fpr_user_turn": rate_with_ci(sum(B4u[c]), len(b4))}
    for k in bl4a:
        h4["baselines"][k] = {"attack_recall": rate_with_ci(sum(bl4a[k]), len(a4)),
                              "benign_fpr_untrusted_channel": rate_with_ci(sum(bl4b[k]), len(b4))}
    h4["neutralisation"] = summarise(c4raw, c4neu, {c: (A4[c], B4[c]) for c in A4})
    h4["raw"] = {"attack": A4, "benign": B4, "benign_user_turn": B4u,
                 "compliance_raw": c4raw, "compliance_framed": c4neu, "attack_ids": ids}
    out["holdouts"]["holdout4"] = h4
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
