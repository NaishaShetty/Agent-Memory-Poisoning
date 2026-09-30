"""Phase 17 (external review round 4, 2026-09-30) -- AgentPoison, measured against the
AUTHORS' OWN published attack material instead of only this project's reconstruction.

The reviewer's objection: *"The AgentPoison reconstruction is weak. It's the least
retrievable of the 7 families, so every AgentPoison defense number is measured against an
attack that barely works. Re-optimize the trigger properly against all-MiniLM-L6-v2, or
drop AgentPoison from headline claims."*

This project takes the second option for headline claims (see `BENCHMARK_CARD.md`), and
adds this measurement so the disclosure rests on evidence rather than assertion. No new
trigger is optimized here. Instead, the attack artifacts AgentPoison's own authors
released (github.com/BillChan226/AgentPoison, MIT) -- their poisoned-knowledge templates
and the trigger strings that appear in their released scripts, extracted verbatim by
`phase17/external_attacks.py` -- are measured on the two properties that decide whether an
AgentPoison number means anything:

 1. RETRIEVABILITY, by the same protocol `PHASE17_ROUND5_FIXES.md` §1 used for the
    reconstruction: one shared candidate pool (one memory per attack family + 50 real
    benign memories), embedded with `all-MiniLM-L6-v2` (the model this project's own
    retrieval signals use and the one the reconstruction was optimized against), ranked
    against 300 diverse real LoCoMo questions, counting top-3 appearances. Reported for
    ordinary queries AND for trigger-carrying queries, because a backdoor trigger is not
    supposed to be a universal magnet -- it is supposed to fire on queries that carry it.
    The reconstruction was only ever measured on ordinary queries, which is part of why
    it looked inert.
 2. DETECTION by the live configs, so the defense numbers for AgentPoison-family content
    are stated against the published material and not only against the reconstruction.

What this does NOT do: it does not reproduce the paper's white-box gradient search, and it
does not claim the published trigger tokens transfer to this project's embedding space --
the released scripts carry placeholder trigger lists for the per-corpus optimization step,
so what is measured here is the authors' poisoned-knowledge templates plus the concrete
trigger strings their code actually ships. That is a stronger basis than the reconstruction
and still weaker than running the real attack end to end.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Sequence

import numpy as np

from phase17.stats import rate_with_ci

OUT = Path(__file__).parent / "data" / "agentpoison_published_check.json"
N_QUERIES = 300
N_BENIGN = 50
TOP_K = 3


def _pool_and_labels() -> Dict[str, List[str]]:
    """One representative memory per founding family (this project's reconstruction), the
    published AgentPoison material, and 50 real benign memories."""
    from phase17.external_attacks import external_records
    from phase17.query_trigger_signal import _benign_memories
    from phase17.poison_sets import original_records

    groups: Dict[str, List[str]] = {}
    for r in original_records():
        groups.setdefault(f"reconstruction::{r.family}", []).append(r.text)
    groups["published::agentpoison"] = [r.text for r in external_records() if r.family == "external_agentpoison"]
    groups["published::minja"] = [r.text for r in external_records() if r.family == "external_minja"]
    groups["benign"] = _benign_memories(N_BENIGN)
    return groups


def _triggers() -> Dict[str, str]:
    """Every trigger in play, each read from its own source artifact rather than hardcoded.

    CORRECTION (2026-09-30, found while reviewing this module's own first result): the first
    version tested the reconstruction ONLY against the PUBLISHED triggers, never against the
    trigger it was itself optimized to produce -- which is the same error this module was
    written to correct in `PHASE17_ROUND5_FIXES.md` §1 (measuring a backdoor outside its own
    trigger condition). A backdoor not fired by its own trigger tells you nothing. Both
    families' own triggers are now tested against both families' poison.
    """
    from phase17.external_attacks import AGENTPOISON_TRIGGERS

    out = {f"published_{i}": t for i, t in enumerate(AGENTPOISON_TRIGGERS)}
    for art in sorted(Path("phase4/attacks/agentpoison").glob("milestone4_artifact_*.json")):
        d = json.loads(art.read_text(encoding="utf-8"))
        t = d.get("trigger_text", "").replace("[MASK]", "").strip()
        if t:
            out[f"reconstruction_{art.stem.split('_')[-1]}"] = " ".join(t.split())
    return out


def run() -> dict:
    from phase17.query_trigger_signal import _ap_embed, _reference_queries

    groups = _pool_and_labels()
    names, texts = [], []
    for g, ts in groups.items():
        for t in ts:
            names.append(g)
            texts.append(t)
    queries = _reference_queries()[:N_QUERIES]
    E = _ap_embed(texts)

    out = {"n_pool": len(texts), "n_queries": len(queries), "top_k": TOP_K, "conditions": {}}
    trigs = _triggers()
    out["triggers"] = trigs
    conditions = {"plain_queries": queries}
    for name, trig in trigs.items():
        conditions[f"trigger::{name}"] = [f"{q} {trig}" for q in queries]

    for cond, qs in conditions.items():
        Q = _ap_embed(qs)
        sims = Q @ E.T
        top = np.argsort(-sims, axis=1)[:, :TOP_K]
        hits = np.zeros(len(texts), dtype=int)
        for row in top:
            hits[row] += 1
        per_group: Dict[str, dict] = {}
        for g in groups:
            idx = [i for i, n in enumerate(names) if n == g]
            per_group[g] = rate_with_ci(int(hits[idx].sum()), len(idx) * len(qs))
        out["conditions"][cond] = per_group
        print(cond, {g: f"{v['rate']:.1%}" for g, v in per_group.items()}, flush=True)

    # Detection of the published material by the live configs.
    out["detection"] = {}
    from phase14.defended_retrieval import apply_defense
    from phase17 import arenas
    from phase17.poison_sets import PoisonRecord
    from phase17.semantic_detector import warm_all_tiers

    targets = {"published::agentpoison": groups["published::agentpoison"],
               "published::minja": groups["published::minja"],
               "reconstruction::agentpoison": groups["reconstruction::agentpoison"]}
    warm_all_tiers([t for v in targets.values() for t in v])
    for cfg in ("B9", "B11", "B12", "B13"):
        out["detection"][cfg] = {}
        for gname, texts in targets.items():
            recs = [PoisonRecord(f"AP-{i}", t, "published", "check") for i, t in enumerate(texts)]
            pools, _ = arenas.isolated_arena(recs)
            excl = flag = 0
            for p, r in zip(pools, recs):
                _, dec = apply_defense(cfg, tuple((m.scenario_id, m.content_text) for m in p.memories))
                d = next(x for x in dec if x.memory_id == r.scenario_id)
                excl += d.excluded
                flag += d.action != "ALLOW"
            out["detection"][cfg][gname] = {"excluded": rate_with_ci(excl, len(texts)),
                                            "flagged": rate_with_ci(flag, len(texts))}
            print("detection", cfg, gname, excl, "/", len(texts), flush=True)

    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    print(json.dumps({k: {g: v["rate"] for g, v in d.items()} for k, d in r["conditions"].items()}, indent=1))
    print("DONE")
