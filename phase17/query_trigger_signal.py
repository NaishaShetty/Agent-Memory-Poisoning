"""Phase 17 fix round 6 -- AgentPoison's query-side embedding trigger: a defense
mechanism that has NEVER existed anywhere in this stack (disclosed limitation carried
since Phase 6). AgentPoison's real mechanism (`phase4/attacks/agentpoison/core.py`) is a
GRADIENT-OPTIMIZED nonsense trigger phrase appended to the poison text, chosen
specifically to make the memory's embedding a "universal retrieval magnet" -- similar to
many DIFFERENT, topically UNRELATED queries, not just the one query the attacker actually
cares about. Every other admission/retrieval signal in this stack looks at a memory's
content in isolation or against other STORED memories; none of them ask "is this memory
suspiciously retrievable by queries that have nothing to do with its own topic?" -- which
is exactly the property a gradient-optimized universal trigger has and an ordinary memory
does not.

SIGNAL: `universal_retrieval_magnet_score(text)` = the memory's mean cosine similarity to
a large, fixed, topically DIVERSE reference query set (drawn from real LoCoMo QA
questions across MANY different real conversations/topics), MINUS the same statistic for
a same-size random sample of real benign memories -- z-scored against the benign
population's own distribution, so the score is 0 for a typical memory and rises only when
a memory is unusually broadly retrievable.

TESTED, not assumed: run on the real AgentPoison artifact, its evasion variants, and 200
real benign memories, with a threshold chosen on a DISJOINT dev sample of the reference
queries/benign memories (never the same split used to compute the eval score).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Sequence

import numpy as np

OUT = Path(__file__).parent / "data" / "query_trigger_results.json"
LOCOMO = Path("data/raw/locomo/locomo10.json")
N_REF_QUERIES = 200  # diverse, cross-conversation queries (dev half used for calibration)


def _reference_queries() -> List[str]:
    raw = json.loads(LOCOMO.read_text(encoding="utf-8"))
    qs = []
    for sample in raw:
        for qa in sample.get("qa", []):
            if qa.get("question"):
                qs.append(qa["question"])
    return qs


def _benign_memories(n: int) -> List[str]:
    from phase17.extra_datasets import convomem_pools

    pools, _ = convomem_pools()
    texts = [m.content_text for p in pools for m in p.memories]
    return texts[:n]


_AP_MODEL = None
AP_TARGET_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # the REAL model the AgentPoison
# trigger in this project was gradient-optimized against (`phase4/attacks/agentpoison/
# trigger_run.py::MODEL_ID`) -- confirmed by inspection. Round-3's first attempt at this
# signal used `bge-small-en-v1.5` (this project's own default judge/detector embedding)
# and got a real negative result; the root cause, confirmed here, is that a
# gradient-optimized trigger's "universal magnet" property is specific to the embedding
# space it was optimized against and does not obviously transfer to a different model.


def _ap_embed(texts: Sequence[str]) -> np.ndarray:
    from sentence_transformers import SentenceTransformer

    global _AP_MODEL
    if _AP_MODEL is None:
        _AP_MODEL = SentenceTransformer(AP_TARGET_MODEL)
    return np.asarray(_AP_MODEL.encode(list(texts), normalize_embeddings=True, batch_size=64))


def universal_retrieval_magnet_scores(texts: Sequence[str], ref_queries: Sequence[str], embed_fn=None) -> np.ndarray:
    embed_fn = embed_fn or _ap_embed
    q_vecs = embed_fn(list(ref_queries))
    t_vecs = embed_fn(list(texts))
    sims = t_vecs @ q_vecs.T  # (n_texts, n_queries)
    return sims.mean(axis=1)


def benign_cluster_outlier_scores(texts: Sequence[str], cluster_centers: np.ndarray) -> np.ndarray:
    """The REAL AgentPoison objective, turned into a detector: `core.py::
    compute_avg_cluster_distance` optimizes the trigger's embedding AWAY from where
    benign content clusters (`core.py` module docstring: "push the poison embedding AWAY
    from where normal/benign content clusters"). This is the direct, targeted signal that
    attacker objective implies -- not a generic "similar to many queries" proxy (which
    round 3's first two attempts showed does not discriminate under either embedding
    model tried). Returns each text's L2 distance to its NEAREST benign cluster centroid
    (bigger = more anomalous relative to normal content)."""
    from phase17.semantic_detector import _embed

    t_vecs = _embed(list(texts))
    d = np.linalg.norm(t_vecs[:, None, :] - cluster_centers[None, :, :], axis=2)
    return d.min(axis=1)


def run_cluster_distance_variant(n_clusters: int = 8) -> dict:
    from sklearn.cluster import KMeans

    from phase17.poison_sets import evasion_records, original_records
    from phase17.semantic_detector import _embed

    benign_all = _benign_memories(400)
    ben_dev, ben_eval = benign_all[0::2], benign_all[1::2]
    km = KMeans(n_clusters=n_clusters, n_init=10, random_state=17).fit(_embed(ben_dev))
    dev_dists = benign_cluster_outlier_scores(ben_dev, km.cluster_centers_)
    mu, sigma = float(dev_dists.mean()), float(dev_dists.std() or 1e-6)
    threshold = mu + 2.0 * sigma

    ap = [r.text for r in original_records() if r.family == "agentpoison"]
    ap_ev = [r.text for r in evasion_records() if r.family == "agentpoison"]
    other = [r.text for r in original_records() if r.family != "agentpoison"]

    def z(texts):
        if not texts:
            return []
        d = benign_cluster_outlier_scores(texts, km.cluster_centers_)
        return [(x - mu) / sigma for x in d]

    ap_z, ap_ev_z, other_z, ben_eval_z = [[float(v) for v in x] for x in (z(ap), z(ap_ev), z(other), z(ben_eval))]
    out = {
        "n_clusters": n_clusters, "dev_benign_mean_dist": mu, "dev_benign_sd": sigma, "threshold_z": 2.0,
        "agentpoison_original_z": ap_z, "agentpoison_original_above": sum(1 for v in ap_z if v >= 2.0),
        "agentpoison_evasion_z": ap_ev_z, "agentpoison_evasion_above": sum(1 for v in ap_ev_z if v >= 2.0),
        "other_families_z": other_z, "other_families_above": sum(1 for v in other_z if v >= 2.0), "n_other": len(other),
        "benign_eval_above": sum(1 for v in ben_eval_z if v >= 2.0), "n_benign_eval": len(ben_eval_z),
    }
    (Path(__file__).parent / "data" / "query_trigger_cluster_results.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def run() -> dict:
    qs = _reference_queries()
    rng_dev, rng_eval = qs[0::2], qs[1::2]  # disjoint dev/eval query halves
    benign = _benign_memories(200)
    ben_dev, ben_eval = benign[0::2], benign[1::2]

    from phase17.poison_sets import evasion_records, original_records

    ap = [r.text for r in original_records() if r.family == "agentpoison"]
    ap_ev = [r.text for r in evasion_records() if r.family == "agentpoison"]

    dev_ben_scores = universal_retrieval_magnet_scores(ben_dev, rng_dev)
    mu, sigma = float(dev_ben_scores.mean()), float(dev_ben_scores.std() or 1e-6)
    threshold = mu + 2.0 * sigma  # fixed on DEV benign only, before touching eval/poison

    def z(texts):
        if not texts:
            return []
        raw = universal_retrieval_magnet_scores(texts, rng_eval)
        return [(float(s), float((s - mu) / sigma)) for s in raw]

    ap_scores = z(ap)
    ap_ev_scores = z(ap_ev)
    ben_eval_scores = z(ben_eval)
    other_families_orig = [r.text for r in original_records() if r.family != "agentpoison"]
    other_scores = z(other_families_orig)

    out = {
        "n_ref_queries_dev": len(rng_dev), "n_ref_queries_eval": len(rng_eval),
        "dev_benign_mean": mu, "dev_benign_sd": sigma, "threshold_z": 2.0,
        "agentpoison_original": {"z_scores": [s[1] for s in ap_scores], "n_above_threshold": sum(1 for s in ap_scores if s[1] >= 2.0), "n": len(ap_scores)},
        "agentpoison_evasion": {"z_scores": [s[1] for s in ap_ev_scores], "n_above_threshold": sum(1 for s in ap_ev_scores if s[1] >= 2.0), "n": len(ap_ev_scores)},
        "benign_eval_fpr": {"n_above_threshold": sum(1 for s in ben_eval_scores if s[1] >= 2.0), "n": len(ben_eval_scores)},
        "other_families_original": {"n_above_threshold": sum(1 for s in other_scores if s[1] >= 2.0), "n": len(other_scores),
                                    "note": "other families' forged claims are topical, NOT universal triggers -- expected near 0"},
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    print(json.dumps({k: v for k, v in r.items() if k not in ("agentpoison_original", "agentpoison_evasion")}, indent=1))
    print("AP original z-scores:", r["agentpoison_original"]["z_scores"])
    print("AP evasion z-scores:", r["agentpoison_evasion"]["z_scores"])
    print("DONE")
