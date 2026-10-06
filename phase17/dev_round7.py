"""DEV evaluation of B20/B21 against B13/B14/B17/B18, on both threats, before any hold-out.

Two development beds, both untouched by hold-outs 4 and 5:

  memory poisoning  this project's own 804 attacks and the 1,054 ordinary-benign texts, with the
                    owner's real conversation (LoCoMo sample 0) supplied as evidence -- the
                    deployment the recommendation is about. B14/B17/B18 decisions with evidence
                    are read from `evidence_round6`'s checkpoint, not recomputed.
  injection         the 266 externally-authored dev attacks against 400 toxic-chat dev benign
                    prompts (`toxicchat_dev_benign`, disjoint from hold-out 5). No owner
                    conversation exists for these, so corroboration cannot fire -- the same
                    condition hold-out 5 will be scored under. Dev attacks come from other
                    sources than the benign half; that asymmetry is stated with every number.

THE DECOMPOSITION IS CHECKED, NOT TRUSTED. For every item, B13's own decision is compared with
the OR of `b20_live.b13_components`; the module refuses to report if they disagree anywhere.

The output also records each B13 component's own exclusion rate on the benign side, which is
the attribution that motivated B20 -- re-measured on DEV data, since the original attribution
turned out to have been measured on hold-out items (R7-1).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Sequence

DATA = Path(__file__).parent / "data"
OUT = DATA / "dev_round7.json"
PARTIAL = DATA / "dev_round7_partial.json"
BATCH = 4
COMPS = ("base", "content", "lineage", "worm", "corroboration")


def _deb(texts: Sequence[str]) -> List[bool]:
    from phase17.b18_live import _deberta_scores, deberta_threshold

    thr = deberta_threshold()
    s = _deberta_scores(list(texts))
    return [s[t] >= thr for t in texts]


def _components(texts, prefix, done, key, evidence=None, names=(), source="tool_output"):
    from phase17.b20_live import b13_components

    out = list(done.get(key, []))
    for i in range(len(out), len(texts), BATCH):
        chunk = [(f"{prefix}-{i+j}", t) for j, t in enumerate(texts[i:i + BATCH])]
        c = b13_components(chunk, sources={m: source for m, _ in chunk}, evidence=evidence,
                           evidence_names=names)
        out += [c[m] for m, _ in chunk]
        if (i // BATCH) % 10 == 0:
            done[key] = out
            PARTIAL.write_text(json.dumps(done), encoding="utf-8")
            print(f"    {key} {len(out)}/{len(texts)}", flush=True)
    done[key] = out
    PARTIAL.write_text(json.dumps(done), encoding="utf-8")
    return out


def _decide(cfg, texts, prefix, done, key, source="tool_output"):
    from phase14.defended_retrieval import apply_defense

    out = list(done.get(key, []))
    for i in range(len(out), len(texts), BATCH):
        chunk = tuple((f"{prefix}-{i+j}", t) for j, t in enumerate(texts[i:i + BATCH]))
        ctx = {} if cfg == "B12" else {"sources": {m: source for m, _ in chunk}}
        _, dec = apply_defense(cfg, chunk, **ctx)
        out += [bool(d.excluded) for d in dec]
        if (i // BATCH) % 10 == 0:
            done[key] = out
            PARTIAL.write_text(json.dumps(done), encoding="utf-8")
            print(f"    {key} {len(out)}/{len(texts)}", flush=True)
    done[key] = out
    PARTIAL.write_text(json.dumps(done), encoding="utf-8")
    return out


def _rate(v):
    from phase17.stats import rate_with_ci

    return rate_with_ci(sum(v), len(v))


def run() -> dict:
    from phase17.b20_live import b13_excluded_from_components, b13_provenance_excluded
    from phase17.eval_populations import benign_populations
    from phase17.eval_round6 import _attack_pops
    from phase17.evidence_round6 import _evidence
    from phase17.external_attacks import external_records
    from phase17.stats import paired_delta
    from phase17.toxicchat_dev_benign import dev_benign_texts, verify_disjoint

    assert verify_disjoint(), "toxic-chat dev benign overlaps hold-out 5"
    done = json.loads(PARTIAL.read_text(encoding="utf-8")) if PARTIAL.exists() else {}
    ev = json.loads((DATA / "evidence_round6_partial.json").read_text(encoding="utf-8"))
    evidence, names = _evidence()
    out: Dict = {"note": "DEV ONLY. Hold-outs 4 and 5 are not read by this module.", "beds": {}}
    mismatch = 0

    # ---------------- bed 1: memory poisoning, with the owner's conversation
    atk = {k: v for k, v in _attack_pops().items() if k.startswith("own_")}
    ben = benign_populations()
    ordinary = [p for p in ben if any(s in p for s in ("dataset_arena", "convomem", "perltqa"))]
    vec = {c: {"atk": [], "ben": []} for c in ("B13", "B14", "B17", "B18", "B20", "B21")}
    comp_ben = {k: 0 for k in COMPS}
    n_ben = 0
    for side, pops in (("atk", list(atk)), ("ben", ordinary)):
        for pop in pops:
            texts = [r.text for r in atk[pop]] if side == "atk" else list(ben[pop])
            comps = _components(texts, f"D7{side}-{pop}", done, f"comp:{side}:{pop}", evidence, names)
            b13 = ev[f"B13:{side}:{pop}"]
            b14, b17, b18 = (ev[f"{c}:{side}:{pop}"] for c in ("B14", "B17", "B18"))
            deb = _deb(texts)
            for i, c in enumerate(comps):
                mismatch += b13_excluded_from_components(c) != bool(b13[i])
                p = b13_provenance_excluded(c)
                b20 = bool(b14[i]) or p
                for cfg, v in (("B13", b13[i]), ("B14", b14[i]), ("B17", b17[i]), ("B18", b18[i]),
                               ("B20", b20), ("B21", b20 or deb[i])):
                    vec[cfg][side].append(bool(v))
                if side == "ben":
                    n_ben += 1
                    for k in COMPS:
                        comp_ben[k] += bool(c[k]) and not c["trusted"]
    out["beds"]["memory_poisoning_with_evidence"] = {
        "attacks": "own_* (804)", "benign": "ordinary (1,054), tool_output channel",
        "per_config": {c: {"recall": _rate(v["atk"]), "benign_fpr": _rate(v["ben"]),
                           "discrimination_points": round(100 * (sum(v["atk"]) / len(v["atk"])
                                                                 - sum(v["ben"]) / len(v["ben"])), 1)}
                       for c, v in vec.items()},
        "paired_B20_vs_B17_attacks": paired_delta(vec["B20"]["atk"], vec["B17"]["atk"]),
        "paired_B21_vs_B18_attacks": paired_delta(vec["B21"]["atk"], vec["B18"]["atk"]),
        "b13_component_benign_exclusions": {k: {"k": v, "n": n_ben} for k, v in comp_ben.items()},
    }

    # ---------------- bed 2: injection, matched-platform benign, no evidence
    xa = [r.text for r in external_records()]
    xb = dev_benign_texts()
    vec2 = {c: {"atk": [], "ben": []} for c in ("B12", "B13", "B14", "B17", "B18", "B20", "B21")}
    comp2 = {k: 0 for k in COMPS}
    for side, texts in (("atk", xa), ("ben", xb)):
        comps = _components(texts, f"D7X{side}", done, f"comp:inj:{side}")
        d = {c: _decide(c, texts, f"D7X{side}{c}", done, f"dec:inj:{side}:{c}")
             for c in ("B12", "B13", "B14")}
        deb = _deb(texts)
        for i, c in enumerate(comps):
            mismatch += b13_excluded_from_components(c) != d["B13"][i]
            p = b13_provenance_excluded(c)
            b17 = d["B13"][i] or d["B14"][i]
            b20 = d["B14"][i] or p
            for cfg, v in (("B12", d["B12"][i]), ("B13", d["B13"][i]), ("B14", d["B14"][i]),
                           ("B17", b17), ("B18", b17 or deb[i]), ("B20", b20), ("B21", b20 or deb[i])):
                vec2[cfg][side].append(bool(v))
            if side == "ben":
                for k in COMPS:
                    comp2[k] += bool(c[k])
    out["beds"]["injection_no_evidence"] = {
        "attacks": "external dev (266; InjecAgent, BIPIA, AgentDojo, MINJA, AgentPoison)",
        "benign": "toxic-chat dev (400), disjoint from hold-out 5",
        "caveat": "dev attacks and dev benign come from different sources",
        "per_config": {c: {"recall": _rate(v["atk"]), "benign_fpr": _rate(v["ben"]),
                           "discrimination_points": round(100 * (sum(v["atk"]) / len(v["atk"])
                                                                 - sum(v["ben"]) / len(v["ben"])), 1)}
                       for c, v in vec2.items()},
        "paired_B20_vs_B17_benign": paired_delta(vec2["B20"]["ben"], vec2["B17"]["ben"]),
        "b13_component_benign_exclusions": {k: {"k": v, "n": len(xb)} for k, v in comp2.items()},
    }
    # Per-item decisions persist, so policies built on them (compose_dev) need no re-run.
    out["raw_injection"] = vec2
    out["raw_memory_poisoning"] = vec
    if mismatch:
        raise SystemExit(f"the component decomposition disagrees with B13 on {mismatch} items; "
                         f"B20 would not be B13 minus a rule")
    out["decomposition_check"] = "OR of b13_components == B13's own exclusion on every item: verified"
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    print(r["decomposition_check"])
    for bed, b in r["beds"].items():
        print(f"\n### {bed}: attacks={b['attacks']}  benign={b['benign']}")
        for c, v in b["per_config"].items():
            print(f"  {c}: recall {v['recall']['rate']:6.1%}  benign FPR {v['benign_fpr']['k']:4d}/"
                  f"{v['benign_fpr']['n']} = {v['benign_fpr']['rate']:6.1%}  discrimination "
                  f"{v['discrimination_points']:+.1f}")
        print("  B13 components firing on benign:", {k: v["k"] for k, v in b["b13_component_benign_exclusions"].items()})
    print("DONE")
