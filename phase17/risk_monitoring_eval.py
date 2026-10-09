"""The first evaluation of Phase 10's risk-weighted MONITORING surface (development data only).

`phase6/defense/risk/risk_weighted_monitoring.rank_forensic_targets_by_risk` never adds or removes an
item from an investigation queue -- it only orders it. So its measurable claim is narrow and real:
does ordering the queue by risk put actual poison earlier, so a human reviewer reaches it sooner?

Queue: every development item (own attacks + ordinary benign) that the risk-composed defense B9
does NOT allow -- the mixed set a reviewer would actually face. Each item's RiskEstimate is built
exactly as `phase14.defended_retrieval._b9_actions` builds it (same signals, same rule), in pools of
POOL items (divergence signals are pool-relative), seeded. Ordered two ways: by risk
(`rank_forensic_targets_by_risk`, unmodified) and by the default order, whose expectation is taken
over N_SHUFFLES seeded shuffles (default queues are sorted by id, which carries no information about
poison). Measured: precision in the first 10 / 50 reviewed, average precision, and benign items read
before half the poisons are reached. Nothing is fitted; no model call is made.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

DATA = Path(__file__).parent / "data"
OUT = DATA / "risk_monitoring_eval.json"
OUT_REAL = DATA / "risk_monitoring_eval_realistic.json"
POOL = 20
SEED = 31
N_SHUFFLES = 200


def _estimates(items):
    """(memory_id -> RiskEstimate, memory_id -> action), replicating _b9_actions for one pool."""
    from phase14.defended_retrieval import _signal_context
    from phase6.defense.admission.reasoning_guard import compute_signals as admission_signals
    from phase6.defense.policy.states import UNASSESSED
    from phase6.defense.retrieval.embedding_signals import pool_consensus_divergence_signals_semantic
    from phase6.defense.retrieval.signals import pool_consensus_divergence_signals
    from phase6.defense.risk.risk_action import action_for_risk_estimate
    from phase6.defense.risk.risk_score import GROUPED_GATED_ADMISSION_CORROBORATED, compute_memory_risk_score
    from phase6.defense.sleeper.signals import imperative_write_directive_signal
    from phase8.detection.activation_shape_signal import activation_shape_signal

    contents = [t for _, t in items]
    div = pool_consensus_divergence_signals(contents)
    sem, _ = pool_consensus_divergence_signals_semantic(contents)
    est, act = {}, {}
    for (mid, text), d, sd in zip(items, div, sem):
        ctx = _signal_context(mid, text)
        sig = {**admission_signals(ctx), **d, "semantic_consensus_divergence_score": sd["consensus_divergence_score"],
               **imperative_write_directive_signal(ctx), **activation_shape_signal(ctx), "dormancy_activation_score": 1.0}
        e = compute_memory_risk_score(mid, sig, rule=GROUPED_GATED_ADMISSION_CORROBORATED)
        est[mid], act[mid] = e, action_for_risk_estimate(e, current_security_state=UNASSESSED)
    return est, act


def _metrics(order, poison):
    lab = [i in poison for i in order]
    n_p = sum(lab)
    ap, hits = 0.0, 0
    for k, y in enumerate(lab, 1):
        if y:
            hits += 1
            ap += hits / k
    half, seen, benign_before = (n_p + 1) // 2, 0, 0
    for y in lab:
        if y:
            seen += 1
            if seen >= half:
                break
        else:
            benign_before += 1
    return {"precision_at_10": sum(lab[:10]) / min(10, len(lab)), "precision_at_50": sum(lab[:50]) / min(50, len(lab)),
            "average_precision": ap / n_p if n_p else None, "benign_before_half_the_poison": benign_before}


def run() -> dict:
    from phase17.epistemic_quarantine import _dev_sets
    from phase6.defense.risk.risk_weighted_monitoring import rank_forensic_targets_by_risk

    recs, _ca, btexts, _cb, _s = _dev_sets()
    items = [(r.scenario_id, r.text) for r in recs] + [(f"BEN-{i}", t) for i, t in enumerate(btexts)]
    poison = {r.scenario_id for r in recs}
    rng = random.Random(SEED)
    rng.shuffle(items)
    est, act = {}, {}
    for i in range(0, len(items), POOL):
        e, a = _estimates(items[i:i + POOL])
        est.update(e)
        act.update(a)
    queue = sorted(mid for mid, a in act.items() if a != "ALLOW")         # the default: sorted by id
    by_risk = [t for _, t in rank_forensic_targets_by_risk([("memory", m) for m in queue], est)]
    risk_m = _metrics(by_risk, poison)
    shuf = []
    for s in range(N_SHUFFLES):
        q = list(queue)
        random.Random(1000 + s).shuffle(q)
        shuf.append(_metrics(q, poison))
    default_m = {k: round(sum(x[k] for x in shuf) / len(shuf), 4) for k in risk_m}
    out = {"n_items": len(items), "n_poison": len(poison), "queue_size": len(queue),
           "poison_in_queue": sum(m in poison for m in queue),
           "base_rate_in_queue": round(sum(m in poison for m in queue) / max(1, len(queue)), 4),
           "risk_ordered": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in risk_m.items()},
           "default_order_expected": default_m,
           "id_sorted_default": _metrics(queue, poison),
           "actions": {a: sum(x == a for x in act.values()) for a in sorted(set(act.values()))}}
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def run_realistic() -> dict:
    """SECOND DESIGN, added after the first was diagnosed (both reported). The first design's pools
    were random mixes of unrelated items, where lexical consensus divergence is positive for every
    item, so B9 routed ~91% of everything to REQUIRE_VALIDATION -- an artifact of the pooling, not a
    property of realistic retrieval. Here each pool is a REAL retrieval: the top 20 memories for one
    harm-study task from the owner's store, with the poison present (the addendum-5 setting). Per
    pool: the items B9 does not allow form that retrieval's review list; measured is how often the
    poison is in the list and ranked FIRST under risk ordering, against the default order's
    expectation (1 / list length when the poison is listed)."""
    import numpy as np

    from phase17 import harm_study_v2 as H
    from phase17.risk_weighted_retrieval_eval import N_POOL
    from phase6.defense.risk.risk_weighted_monitoring import rank_forensic_targets_by_risk

    model = H._retriever()
    rng = random.Random(17)
    rows = []
    for idx, (r, fam) in enumerate(H._records(15, 30, 60, 17)):
        spec = H.EXTERNAL_TASK if fam == "external" else H.TASKS[fam]
        full = H._store_for(H.HARM_SAMPLES[idx % len(H.HARM_SAMPLES)]) + [(r.scenario_id, r.text)]
        rng.shuffle(full)
        v = model.encode([spec["task"]] + [t for _, t in full], normalize_embeddings=True)
        sims = v[1:] @ v[0]
        pool = [full[i] for i in np.argsort(-sims)[:N_POOL]]
        if not any(m == r.scenario_id for m, _ in pool):
            pool = pool[:-1] + [(r.scenario_id, r.text)]
        est, act = _estimates(pool)
        q = sorted(m for m, a in act.items() if a != "ALLOW")
        ranked = [t for _, t in rank_forensic_targets_by_risk([("memory", m) for m in q], est)]
        rows.append({"listed": r.scenario_id in q, "list_len": len(q),
                     "first_by_risk": bool(ranked) and ranked[0] == r.scenario_id,
                     "benign_listed": sum(1 for m in q if m != r.scenario_id)})
        if (idx + 1) % 50 == 0:
            print(f"  {idx + 1}/309", flush=True)
    listed = [x for x in rows if x["listed"]]
    out = {"n_retrievals": len(rows), "poison_listed": len(listed),
           "mean_list_length": round(sum(x["list_len"] for x in rows) / len(rows), 2),
           "mean_benign_listed_per_retrieval": round(sum(x["benign_listed"] for x in rows) / len(rows), 2),
           "poison_first_by_risk": sum(x["first_by_risk"] for x in listed),
           "poison_first_expected_default": round(sum(1 / x["list_len"] for x in listed), 1),
           "note": "second design (realistic retrieval pools), added after the first design's pooling was "
                   "found to inflate the queue; both are reported"}
    OUT_REAL.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    import sys

    if "realistic" in sys.argv:
        print(json.dumps(run_realistic(), indent=1))
        raise SystemExit(0)
    r = run()
    print(json.dumps({k: v for k, v in r.items()}, indent=1))
    print("DONE")
