"""The one evaluation of B19 (shape gate + B13), with the accounting fixed in `b19_live` first.

Reports, for every population, the MALFORMED / EXCLUDED split rather than a single number, so
the gate cannot take credit for detection it did not perform:

  not_admitted = malformed + excluded     the security-relevant quantity
  detected     = excluded only            poison detection; malformed never counts
  benign cost  = malformed + excluded     on the full and benign-as-a-memory denominators

Own attacks are scored WITH the owner's conversation supplied, because scoring them without it
leaves B13's corroboration inert and this project already published a round of tables that way.
Hold-out 3 has no owner conversation, so its attacks are scored without one -- the same
condition every other configuration faced on it.

On hold-out 3 the provenance numbers here are a FLOOR: that corpus has no owner conversation,
so corroboration is inapplicable and no evidence is supplied. Own attacks ARE scored with the
conversation supplied, so those are not floors.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Sequence

OUT = Path(__file__).parent / "data" / "eval_b19.json"
PARTIAL = Path(__file__).parent / "data" / "eval_b19_partial.json"
BATCH = 4


def _decide(cfg: str, texts: Sequence[str], prefix: str, *, evidence=None, names=(),
            source="tool_output", key="", done: Dict = None):
    from phase14.defended_retrieval import HARD_MITIGATION_ACTIONS, apply_defense

    done = done if done is not None else {}
    out = list(done.get(key, []))
    start = (len(out) // BATCH) * BATCH
    out = out[:start]
    for i in range(start, len(texts), BATCH):
        chunk = [(f"{prefix}-{i+j}", t) for j, t in enumerate(texts[i:i + BATCH])]
        ctx = {"sources": {m: source for m, _ in chunk}}
        if evidence:
            ctx["evidence"] = evidence
            ctx["evidence_names"] = names
        _, dec = apply_defense(cfg, tuple(chunk), **ctx)
        for d in dec:
            out.append("MALFORMED" if d.action == "MALFORMED"
                       else ("EXCLUDED" if d.action in HARD_MITIGATION_ACTIONS else "ADMITTED"))
        if key and (i // BATCH) % 20 == 0:
            done[key] = out
            PARTIAL.write_text(json.dumps(done), encoding="utf-8")
            print(f"    {cfg} {prefix} {len(out)}/{len(texts)}", flush=True)
    if key:
        done[key] = out
        PARTIAL.write_text(json.dumps(done), encoding="utf-8")
    return out


def _summ(labels: Sequence[str], valid_mask: Sequence[bool] = None) -> dict:
    from phase17.stats import rate_with_ci

    n = len(labels)
    mal = sum(x == "MALFORMED" for x in labels)
    exc = sum(x == "EXCLUDED" for x in labels)
    d = {"n": n, "malformed": mal, "excluded": exc,
         "not_admitted": rate_with_ci(mal + exc, n),
         "detected_as_poison": rate_with_ci(exc, n)}
    if valid_mask is not None and len(valid_mask) == n:
        idx = [i for i, v in enumerate(valid_mask) if v]
        if idx:
            d["on_valid_subset"] = {
                "n": len(idx),
                "not_admitted": rate_with_ci(
                    sum(labels[i] in ("MALFORMED", "EXCLUDED") for i in idx), len(idx)),
                "malformed": sum(labels[i] == "MALFORMED" for i in idx),
                "excluded": sum(labels[i] == "EXCLUDED" for i in idx)}
    return d


def run() -> dict:
    from phase17.eval_populations import benign_populations
    from phase17.eval_round6 import _attack_pops
    from phase17.evidence_round6 import _evidence
    from phase17.holdout3_corpus import attack_records, benign_texts, verify_frozen

    assert verify_frozen(), "hold-out 3 no longer matches its frozen digest"
    done = json.loads(PARTIAL.read_text(encoding="utf-8")) if PARTIAL.exists() else {}
    ev, names = _evidence()
    own = {k: v for k, v in _attack_pops().items() if k.startswith("own_")}
    ben = benign_populations()
    h3a = [r.text for r in attack_records()]
    h3b = list(benign_texts())

    # benign-as-a-memory mask for hold-out 3, from the audit
    mask = None
    p = Path(__file__).parent / "data" / "benign_validity_audit.json"
    if p.exists():
        f = json.loads(p.read_text(encoding="utf-8"))["populations"].get("holdout3_matched_benign")
        if f and len(f["valid_flags"]) == len(h3b):
            mask = [bool(x) for x in f["valid_flags"]]

    out = {"accounting": "not_admitted = malformed + excluded; detected = excluded only",
           "own_attacks_scored_with_evidence": True, "populations": {}}

    print("own attacks (with the owner's conversation supplied)", flush=True)
    agg: List[str] = []
    for pop, recs in own.items():
        lab = _decide("B19", [r.text for r in recs], f"B19-{pop}", evidence=ev, names=names,
                      key=f"own:{pop}", done=done)
        out["populations"][pop] = _summ(lab)
        agg += lab
        print(f"  {pop:24s} not admitted {out['populations'][pop]['not_admitted']['k']}/"
              f"{len(lab)} (malformed {out['populations'][pop]['malformed']})", flush=True)
    out["own_attacks_aggregate"] = _summ(agg)

    print("ordinary benign (the regression check)", flush=True)
    bagg: List[str] = []
    for pop, texts in ben.items():
        lab = _decide("B19", list(texts), f"B19B-{pop}", evidence=ev, names=names,
                      key=f"ben:{pop}", done=done)
        out["populations"][f"benign::{pop}"] = _summ(lab)
        bagg += lab
    out["ordinary_benign_aggregate"] = _summ(bagg)
    print(f"  ordinary benign not admitted {out['ordinary_benign_aggregate']['not_admitted']['k']}"
          f"/{len(bagg)}", flush=True)

    print("hold-out 3 (no owner conversation exists for it)", flush=True)
    la = _decide("B19", h3a, "B19-ITW", key="h3:attack", done=done)
    lb = _decide("B19", h3b, "B19-ITWBEN", key="h3:benign", done=done)
    out["holdout3_attacks"] = _summ(la)
    out["holdout3_benign"] = _summ(lb, mask)
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    print("\n### B19 (shape gate + B13)")
    a = r["own_attacks_aggregate"]
    b = r["ordinary_benign_aggregate"]
    print(f"  own attacks (with evidence)   not admitted {a['not_admitted']['k']}/{a['n']} = "
          f"{a['not_admitted']['rate']:.1%}  (detected {a['detected_as_poison']['rate']:.1%}, "
          f"malformed {a['malformed']})")
    print(f"  ordinary benign               not admitted {b['not_admitted']['k']}/{b['n']} = "
          f"{b['not_admitted']['rate']:.2%}")
    ha, hb = r["holdout3_attacks"], r["holdout3_benign"]
    print(f"  hold-out 3 attacks            not admitted {ha['not_admitted']['k']}/{ha['n']} = "
          f"{ha['not_admitted']['rate']:.1%}  (malformed {ha['malformed']}, excluded {ha['excluded']})")
    print(f"  hold-out 3 benign             not admitted {hb['not_admitted']['k']}/{hb['n']} = "
          f"{hb['not_admitted']['rate']:.1%}  (malformed {hb['malformed']}, excluded {hb['excluded']})")
    if "on_valid_subset" in hb:
        v = hb["on_valid_subset"]
        print(f"    on benign-as-a-memory only  {v['not_admitted']['k']}/{v['n']} = "
              f"{v['not_admitted']['rate']:.1%}")
    print("DONE")
