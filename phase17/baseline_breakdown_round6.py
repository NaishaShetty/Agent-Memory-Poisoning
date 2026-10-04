"""Per-population comparison of EVERY config against EVERY published baseline (round 6).

`baseline_breakdown.py` could only cover B12-B14, because it re-reads `eval_round5.json` and
round 5 predates B15/B16/B17. That left the three newest configs with no per-population baseline
comparison at all -- the open item from the round-6 write-up.

It is closable with no new model calls. Every one of the 3,528 attack texts across all 15
populations already has a cached score for all five published baselines (verified: 100%
coverage, 0 missing), and `eval_round6.json` now persists per-item config decisions. So:

  * config recall per population comes from the saved raw decisions;
  * B16's static decisions ARE B15's by construction (`static_equivalence` confirmed this on 60
    real records, 0 differing), so B16 is reported as B15 with that stated rather than re-run;
  * B17 = exclude if B13 or B14 excludes, computed from the same raw decisions;
  * baseline recall comes from cached scores and the thresholds frozen in `eval_round5.json`,
    at BOTH the dev-calibrated and the oracle-matched threshold.

Thresholds are reused verbatim and never re-fitted here -- re-fitting a baseline's threshold on
the populations it is then scored against is how a baseline gets quietly handicapped.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List

DATA = Path(__file__).parent / "data"
EVAL = DATA / "eval_round6.json"
SCORES = DATA / "external_baseline_scores.json"
R5 = DATA / "eval_round5.json"
OUT = DATA / "baseline_breakdown_round6.json"

BASELINES = ("llama_guard3", "deberta_pi_v2", "perplexity_gpt2", "llm_prompt_qwen", "llm_prompt_llama31")
CONFIGS = ("B12", "B13", "B14", "B15", "B16", "B17")


def _key(name: str, text: str) -> str:
    return name + ":" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


def _config_decisions(d: dict, cfg: str, key: str) -> List[bool]:
    """Excluded flags for one config on one population, from saved raw output.

    B16 and B17 are derived rather than stored: B16 is B15 with an empty ledger (identical by
    construction), B17 is the B13/B14 union. Deriving them keeps this consistent with the
    dispatcher instead of depending on a re-run that could drift from it.
    """
    if cfg == "B16":
        return [bool(e) for e, _ in d["raw"]["B15"][key]]
    if cfg == "B17":
        a, b = d["raw"]["B13"][key], d["raw"]["B14"][key]
        return [bool(x[0] or y[0]) for x, y in zip(a, b)]
    return [bool(e) for e, _ in d["raw"][cfg][key]]


def run() -> dict:
    from phase17.eval_round6 import _attack_pops, _benign_pops
    from phase17.stats import rate_with_ci

    d = json.loads(EVAL.read_text(encoding="utf-8"))
    scores = json.loads(SCORES.read_text(encoding="utf-8"))
    thr = json.loads(R5.read_text(encoding="utf-8"))["baseline_thresholds"]
    attacks, benign = _attack_pops(), _benign_pops()

    missing = {b: sum(1 for rs in attacks.values() for r in rs if _key(b, r.text) not in scores)
               for b in BASELINES}
    rows: Dict[str, dict] = {}
    for pop, recs in attacks.items():
        key = f"attack::{pop}"
        row = {"n": len(recs), "group": "own" if pop.startswith("own_") else "external"}
        for cfg in CONFIGS:
            v = _config_decisions(d, cfg, key)
            row[cfg] = rate_with_ci(sum(v), len(v))
        for b in BASELINES:
            s = [scores.get(_key(b, r.text)) for r in recs]
            s = [x for x in s if x is not None]
            for tname in ("dev", "oracle"):
                t = thr[b][tname]
                row[f"{b}@{tname}"] = rate_with_ci(sum(x >= t for x in s), len(s))
        rows[pop] = row

    # Benign false positives, same treatment, so a recall column is never read without its cost.
    ben: Dict[str, dict] = {}
    ordinary = [k for k in benign if any(t in k for t in ("dataset_arena", "convomem", "perltqa",
                                                          "agentdojo_tool"))]
    for pop, texts in benign.items():
        key = f"benign::{pop}"
        row = {"n": len(texts), "ordinary": pop in ordinary}
        for cfg in CONFIGS:
            if key in d["raw"].get("B15", {}) or key in d["raw"].get("B13", {}):
                v = _config_decisions(d, cfg, key)
                row[cfg] = rate_with_ci(sum(v), len(v))
        for b in BASELINES:
            s = [scores.get(_key(b, t)) for t in texts]
            s = [x for x in s if x is not None]
            if s:
                for tname in ("dev", "oracle"):
                    t = thr[b][tname]
                    row[f"{b}@{tname}"] = rate_with_ci(sum(x >= t for x in s), len(s))
        ben[pop] = row

    def agg(group=None):
        keys = [p for p, r in rows.items() if group is None or r["group"] == group]
        n = sum(rows[p]["n"] for p in keys)
        out = {"n": n, "n_populations": len(keys)}
        for col in list(CONFIGS) + [f"{b}@{t}" for b in BASELINES for t in ("dev", "oracle")]:
            k = sum(rows[p][col]["k"] for p in keys if col in rows[p])
            out[col] = {"k": k, "n": n, "rate": round(k / max(n, 1), 4)}
        return out

    def ben_agg():
        n = sum(ben[p]["n"] for p in ordinary)
        out = {"n": n, "populations": ordinary}
        for col in list(CONFIGS) + [f"{b}@{t}" for b in BASELINES for t in ("dev", "oracle")]:
            k = sum(ben[p][col]["k"] for p in ordinary if col in ben[p])
            out[col] = {"k": k, "n": n, "rate": round(k / max(n, 1), 5)}
        return out

    out = {"configs": list(CONFIGS), "baselines": list(BASELINES),
           "thresholds_reused_from": "eval_round5.json::baseline_thresholds (never re-fitted here)",
           "n_missing_baseline_scores": missing,
           "derived_configs": {"B16": "= B15 statically (empty ledger; static_equivalence 0/60 differing)",
                               "B17": "= B13 OR B14, from the same saved raw decisions"},
           "by_population": rows, "benign_by_population": ben,
           "aggregate_own": agg("own"), "aggregate_external": agg("external"),
           "aggregate_all": agg(), "ordinary_benign_fpr": ben_agg(),
           "why_not_to_cite_the_aggregate": (
               "The all-populations aggregate is 72% external by item count, and those corpora "
               "are the prompt-injection baselines' training distribution. Cite the split."),
           "no_model_calls": True}
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    cols = ["B13", "B14", "B15", "B17", "deberta_pi_v2@dev", "llama_guard3@dev", "llm_prompt_llama31@dev"]
    hdr = f"{'population':24s} {'n':>5s} " + " ".join(f"{c.split('@')[0][:9]:>9s}" for c in cols)
    for g in ("own", "external"):
        print(f"\n### {g}\n{hdr}")
        for p, v in sorted(r["by_population"].items(), key=lambda kv: (kv[1]["group"] != g, -kv[1]["n"])):
            if v["group"] != g:
                continue
            print(f"  {p:22s} {v['n']:5d} " + " ".join(f"{v[c]['rate']:8.1%} " for c in cols))
    for k in ("aggregate_own", "aggregate_external", "aggregate_all"):
        a = r[k]
        print(f"\n{k:20s} n={a['n']:5d} " + " ".join(f"{c.split('@')[0][:9]} {a[c]['rate']:.1%}" for c in cols))
    f = r["ordinary_benign_fpr"]
    print(f"\nordinary-benign FPR (n={f['n']}): " +
          "  ".join(f"{c.split('@')[0][:9]} {f[c]['k']}/{f['n']}" for c in cols))
    print("DONE")
