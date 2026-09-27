"""Phase 17 -- 'attribution ambiguity' fix: PROBABILISTIC multi-source attribution.

Phase 13 reports a derived memory built from several sources as a binary MULTIPLE_POSSIBLE_SOURCES
(lineage ambiguity 21.1%). That is correct but uninformative: it does not say WHICH candidates the
derived memory reflects or how strongly. Here every candidate source gets a calibrated probability of
having contributed, from the same clause-level similarity Phase 12 uses to decide 'reflected', through a
logistic calibration fitted on DEV derived memories only; evaluation on disjoint held-out derived memories
with AUC, exact-set recovery (top-k = the true sources), Brier score and expected calibration error.
Derived memories are REAL local-LLM consolidations (qwen2.5:7b, the Phase 12 prompt) of 1-3 real sources
mixed with same-conversation distractors that were NOT in the context (hard negatives). Persisted to
`phase17/data/prob_attribution.json`."""

from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np

OUT = Path(__file__).parent / "data" / "prob_attribution.json"
N_DEV, N_EVAL, N_DIST = 40, 60, 3


def build(seed: int = 17) -> dict:
    from phase11.relational_signals.locomo_qa_counterfactuals import flat_counterfactual_pool
    from phase12.propagation.ollama_provider import OllamaProvider
    from phase12.propagation.propagation_rate import _consolidation_messages, _get_embedding_model, _max_clause_similarity
    from phase3.evaluation.llm.provider import GenerationConfig

    pool = [m.declarative_text for m in flat_counterfactual_pool()]
    rng, prov, model = random.Random(seed), OllamaProvider(model="qwen2.5:7b"), _get_embedding_model()
    cfg = GenerationConfig(temperature=0.0, seed=42, max_tokens=200, enable_thinking=False, n_ctx=2048, request_timeout_sec=180.0)
    items = []
    for i in range(N_DEV + N_EVAL):
        k = 1 + i % 3
        base = rng.randrange(len(pool) - 12)
        window = list(range(base, base + 12))            # same-conversation neighbourhood -> hard negatives
        rng.shuffle(window)
        srcs, negs = window[:k], window[k:k + N_DIST]
        context = [pool[j] for j in srcs] + [pool[j] for j in window[k + N_DIST:k + N_DIST + 1]]  # 1 extra context filler counted as source
        true_ids = srcs + window[k + N_DIST:k + N_DIST + 1]
        summary = prov.generate(_consolidation_messages(tuple(context)), cfg).text.strip()
        cands = [(j, True) for j in true_ids] + [(j, False) for j in negs]
        items.append({"id": i, "split": "dev" if i < N_DEV else "eval", "k_true": len(true_ids), "summary": summary,
                      "cands": [{"idx": j, "true": t, "sim": _max_clause_similarity(model, summary, pool[j])} for j, t in cands]})
    OUT.write_text(json.dumps(items, indent=1), encoding="utf-8")
    return {"n": len(items)}


def analyze() -> dict:
    from sklearn.linear_model import LogisticRegression

    from phase17.judge_scores import roc_auc

    items = json.loads(OUT.read_text(encoding="utf-8"))
    flat = lambda sp: [(c["sim"], c["true"], it) for it in items if it["split"] == sp for c in it["cands"]]
    dev, ev = flat("dev"), flat("eval")
    lr = LogisticRegression().fit(np.array([[s] for s, _, _ in dev]), [int(t) for _, t, _ in dev])
    prob = lambda s: float(lr.predict_proba([[s]])[0, 1])
    p = [prob(s) for s, _, _ in ev]; y = np.array([int(t) for _, t, _ in ev])
    auc = roc_auc([x for x, t in zip(p, y) if t], [x for x, t in zip(p, y) if not t])
    brier = float(np.mean((np.array(p) - y) ** 2))
    bins = np.linspace(0, 1, 6); ece = 0.0
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = [(pp, yy) for pp, yy in zip(p, y) if lo <= pp < hi or (hi == 1 and pp == 1)]
        if m:
            ece += len(m) / len(p) * abs(np.mean([a for a, _ in m]) - np.mean([b for _, b in m]))
    exact = tot = 0
    for it in items:
        if it["split"] != "eval":
            continue
        ranked = sorted(it["cands"], key=lambda c: -c["sim"])[: it["k_true"]]
        exact += all(c["true"] for c in ranked); tot += 1
    # binary Phase-13-style rule: 'ambiguous' if >1 candidate above the Phase 12 reflect threshold, never says which
    from phase12.propagation.propagation_rate import PROPAGATION_REFLECTS_POISON_THRESHOLD as T
    bin_single_correct = sum(1 for it in items if it["split"] == "eval" and sum(c["sim"] >= T for c in it["cands"]) >= 1 and
                             all(c["true"] for c in it["cands"] if c["sim"] >= T))
    res = {"n_derived_dev": N_DEV, "n_derived_eval": N_EVAL, "n_candidates_eval": len(ev), "calibrated_auc": auc,
           "brier": brier, "ece_5bin": float(ece), "exact_top_k_set_recovery": [exact, tot],
           "binary_rule_precision_only_true_above_threshold": [bin_single_correct, tot],
           "calibration": {"coef": float(lr.coef_[0, 0]), "intercept": float(lr.intercept_[0])}}
    Path(OUT.parent / "prob_attribution_results.json").write_text(json.dumps(res, indent=2))
    return res


if __name__ == "__main__":
    if not OUT.exists():
        build()
    print(analyze())
