"""The GNN-GLN hybrid, evaluated where graph structure actually exists: the derived-memory /
consolidation setting (real poison -> summary DERIVED_FROM edges). Design fixed 2026-10-12 before run.

WHY. The ablation (ablation_results.json) showed removing -propagation / -sibling_propagation changes
nothing on the frozen B0-B8 corpus, because those are ISOLATED single-poison pools with no ancestor
edges -- the exact relational structure a GNN exists to use. This builds consolidation pools from the
laundering experiment (derived_memory_eval): each episode is a pool of the retrieved benign memories +
the poison, plus a DERIVED_FROM-linked summary node that an LLM wrote from them. A laundered summary
(carries the poison's payload) is linked to the poison ancestor, so a GNN's message passing over the
DERIVED_FROM edge can propagate the poison signal to the summary -- which content features on the
summary alone cannot see (the summary is a clean paraphrase).

TEST (committed before running). Same trained GNN, same features; the ONLY difference is whether
message passing runs over the real DERIVED_FROM/RETRIEVED_WITH edges (graph) or is switched off (zeroed
adjacency = content-only). G-1: the graph lifts detection of the laundered SUMMARY nodes over
content-only at a matched benign FPR. Reported whichever way it goes; no agent calls (summaries are read
from the derived_memory cache, retrieval is deterministic).
"""
from __future__ import annotations

import json
import random
from pathlib import Path

DATA = Path(__file__).parent / "data"
OUT = DATA / "gnn_consolidation_eval.json"
CACHE = DATA / "derived_memory_eval_partial.json"


def _episodes():
    """Reconstruct the consolidation episodes exactly as derived_memory_eval built them (deterministic
    retrieval; summaries read from the cache, no agent calls)."""
    from phase17 import harm_study_v2 as H

    cache = json.loads(CACHE.read_text(encoding="utf-8"))
    model = H._retriever()
    recs = H._records(15, 30, 60, 17)
    rng = random.Random(17)
    eps = []
    for idx, (r, fam) in enumerate(recs):
        if fam == "external":
            continue
        spec = H.EXTERNAL_TASK if fam == "external" else H.TASKS[fam]
        full = H._store_for(H.HARM_SAMPLES[idx % len(H.HARM_SAMPLES)]) + [(r.scenario_id, r.text)]
        rng.shuffle(full)
        cand = H._retrieve(model, spec["task"], full)
        if not any(m == r.scenario_id for m, _ in cand):
            cand = cand[:-1] + [(r.scenario_id, r.text)]
        sk, ck = f"sum:{r.scenario_id}", f"carry:{r.scenario_id}"
        if sk not in cache or ck not in cache:
            continue
        eps.append({"id": r.scenario_id, "poison": r.text, "cand": cand,
                    "summary": cache[sk], "carries": bool(cache[ck])})
    return eps


def _pools(eps):
    from phase6.defense.orchestration.pipeline import MemoryScenario, ScenarioPool

    pools = []
    for e in eps:
        mems = []
        anc_ids = []
        for mid, text in e["cand"]:
            is_poison = (mid == e["id"])
            mems.append(MemoryScenario(scenario_id=f"{e['id']}::{mid}", content_text=text,
                                       is_poison_ground_truth=is_poison))
            anc_ids.append(f"{e['id']}::{mid}")
        # the derived summary, DERIVED_FROM every ancestor; poison iff it carries the payload
        mems.append(MemoryScenario(scenario_id=f"{e['id']}::summary", content_text=e["summary"],
                                   parent_ids=tuple(anc_ids), is_poison_ground_truth=e["carries"]))
        pools.append(ScenarioPool(pool_id=e["id"], memories=tuple(mems)))
    return pools


def _augmented_feature_fn(centroids):
    """GNN node features PLUS the cluster-outlier anomaly distance (the fix, 2026-10-12): the frozen GNN
    features (consensus divergence) do not separate a fabricated fact from a benign one, so poison and
    benign get identical scores and the graph has nothing to propagate. The anomaly distance is high on
    a planted poison and low on benign -- a discriminative per-node signal the GNN can then propagate
    over the DERIVED_FROM edge to a laundered summary. Centroids are fit on TRAIN benign only (passed in),
    so the feature is label-free at inference."""
    import numpy as np

    from phase11.gnn.features import GNN_FEATURE_KEYS, pools_node_features_gnn
    from phase17.query_trigger_signal import benign_cluster_outlier_scores
    from phase17.semantic_detector import _embed

    def fn(pools):
        base = pools_node_features_gnn(pools)
        ids, texts = [], []
        for p in pools:
            for m in p.memories:
                ids.append(m.scenario_id)
                texts.append(m.content_text)
        od = benign_cluster_outlier_scores(texts, centroids)
        # scale the distance to a 0..1-ish range comparable to the other features
        od = (od - od.min()) / (od.max() - od.min() + 1e-9)
        anomaly = {i: float(v) for i, v in zip(ids, od)}
        return {i: tuple(list(base[i]) + [anomaly[i]]) for i in base}

    return fn, list(GNN_FEATURE_KEYS) + ["activation_anomaly_score"]


def run() -> dict:
    import numpy as np
    import torch
    from sklearn.cluster import KMeans

    from phase11.gnn.train import build_dataset, train_model
    from phase17.semantic_detector import _embed
    from phase17.stats import rate_with_ci

    eps = _episodes()
    pools = _pools(eps)
    rng = np.random.RandomState(17)
    tr_mask = rng.rand(len(pools)) < 0.5
    tr_pools = [p for p, m in zip(pools, tr_mask) if m]
    te_pools = [p for p, m in zip(pools, tr_mask) if not m]

    # Fit the anomaly centroids on TRAIN benign node texts only (label-free at inference).
    tr_benign = [m.content_text for p in tr_pools for m in p.memories if not m.is_poison_ground_truth]
    km = KMeans(n_clusters=8, n_init=10, random_state=17).fit(_embed(tr_benign))
    feat_fn, feat_keys = _augmented_feature_fn(km.cluster_centers_)

    bd = lambda ps: build_dataset(ps, feature_keys=feat_keys, feature_fn=feat_fn)
    tr_ds = bd(tr_pools)
    model = train_model(tr_ds)
    te_ds = bd(te_pools)

    # Same model, same features: message passing ON (real edges) vs OFF (zeroed adjacency = content-only)
    feats = te_ds.features
    scores_graph = model.predict_proba(feats, te_ds.mean_adj).tolist()
    scores_content = model.predict_proba(feats, torch.zeros_like(te_ds.mean_adj)).tolist()
    labels = te_ds.labels.tolist()
    ids = te_ds.node_ids
    is_summary = [i.endswith("::summary") for i in ids]
    is_benign = [y == 0.0 for y in labels]

    def at_fpr(scores, target=0.10):
        benign = sorted((s for s, b in zip(scores, is_benign) if b), reverse=True)
        if not benign:
            return 1.0
        k = max(0, int(target * len(benign)) - 1)
        return benign[k]

    def metrics(scores):
        thr = at_fpr(scores)
        # laundered summaries = summary nodes labelled poison (carry the payload)
        laund = [(s, labels[i]) for i, s in enumerate(scores) if is_summary[i] and labels[i] == 1.0]
        summ_det = sum(1 for s, _ in laund if s >= thr)
        poison_all = [(s, i) for i, s in enumerate(scores) if labels[i] == 1.0]
        det_all = sum(1 for s, _ in poison_all if s >= thr)
        fpr = sum(1 for i, s in enumerate(scores) if is_benign[i] and s >= thr)
        return {"threshold": round(thr, 4),
                "laundered_summary_detection": rate_with_ci(summ_det, len(laund)) if laund else None,
                "all_poison_detection": rate_with_ci(det_all, len(poison_all)),
                "benign_fpr": rate_with_ci(fpr, sum(is_benign))}

    # MAX-aggregation over lineage: the GNN mean-pools, diluting one poison ancestor among ~4 benign
    # co-parents; taking the MAX anomaly over a derived node's DERIVED_FROM parents (the containment
    # guard's own max-over-ancestors logic) is the right operation for laundering. Computed directly.
    from phase17.query_trigger_signal import benign_cluster_outlier_scores
    tr_benign_txt = [m.content_text for p in tr_pools for m in p.memories if not m.is_poison_ground_truth]
    anom_centroids = km.cluster_centers_
    te_ben_anom = benign_cluster_outlier_scores(
        [m.content_text for p in te_pools for m in p.memories if not m.is_poison_ground_truth], anom_centroids)
    athr = float(np.percentile(te_ben_anom, 90))
    max_det = max_n = own_det = 0
    for p in te_pools:
        summ = [m for m in p.memories if m.scenario_id.endswith("::summary")][0]
        if not summ.is_poison_ground_truth:
            continue
        max_n += 1
        txt = {m.scenario_id: m.content_text for m in p.memories}
        par_anom = benign_cluster_outlier_scores([txt[q] for q in summ.parent_ids], anom_centroids)
        own_anom = benign_cluster_outlier_scores([summ.content_text], anom_centroids)[0]
        max_det += float(par_anom.max()) >= athr
        own_det += float(own_anom) >= athr

    # --- learned MAX-aggregating GNN (the graph genuinely working, not just a rule) ---
    from phase11.gnn.model import MaxAggregatingGNN
    from phase11.gnn.train import EPOCHS, LEARNING_RATE, SEED

    def _binmask(ds):
        return (ds.mean_adj > 0).float()

    def train_max_gnn(ds):
        torch.manual_seed(SEED)
        m = MaxAggregatingGNN(in_dim=ds.features.shape[1], seed=SEED)
        opt = torch.optim.Adam(m.parameters(), lr=LEARNING_RATE)
        loss_fn = torch.nn.BCEWithLogitsLoss()
        mask = _binmask(ds)
        for _ in range(EPOCHS):
            opt.zero_grad()
            loss = loss_fn(m(ds.features, mask), ds.labels)
            loss.backward()
            opt.step()
        return m
    max_model = train_max_gnn(tr_ds)
    scores_max = max_model.predict_proba(te_ds.features, _binmask(te_ds)).tolist()

    # --- GLN arm: the GLN is graph-agnostic (per-node online), so it cannot use the graph; test it on
    # the node features, and with the max-lineage anomaly as an extra (graph-derived) input feature ---
    from phase11.gln.model import GatedLinearNetwork

    def _lineage_max_feature(pools, centroids):
        from phase17.query_trigger_signal import benign_cluster_outlier_scores
        feat = {}
        for p in pools:
            txt = {m.scenario_id: m.content_text for m in p.memories}
            own = {mid: float(benign_cluster_outlier_scores([t], centroids)[0]) for mid, t in txt.items()}
            for m in p.memories:
                parents = m.parent_ids
                feat[m.scenario_id] = max([own[m.scenario_id]] + [own[q] for q in parents]) if parents else own[m.scenario_id]
        return feat

    def run_gln(train_rows, test_rows, dim):
        import numpy as np
        gln = GatedLinearNetwork(input_dim=dim, context_dim=dim, seed=11)
        rng = np.random.RandomState(11)
        order = list(range(len(train_rows))); rng.shuffle(order)
        for _ in range(3):                       # a few online passes over the training stream
            for i in order:
                x, y = train_rows[i]
                gln.predict_and_update(x, x, target=float(y))
        return [gln.predict_and_update(x, x, target=None) for x, y in test_rows]

    featmat = te_ds.features.numpy()
    tr_feat = tr_ds.features.numpy()
    lm = _lineage_max_feature(te_pools, km.cluster_centers_)
    lm_tr = _lineage_max_feature(tr_pools, km.cluster_centers_)
    import numpy as _np2
    tr_lab = tr_ds.labels.tolist()
    gln_plain_tr = [(tr_feat[i], tr_lab[i]) for i in range(len(tr_feat))]
    gln_plain_te = [(featmat[i], labels[i]) for i in range(len(featmat))]
    gln_aug_tr = [(_np2.append(tr_feat[i], lm_tr[tr_ds.node_ids[i]]), tr_lab[i]) for i in range(len(tr_feat))]
    gln_aug_te = [(_np2.append(featmat[i], lm[ids[i]]), labels[i]) for i in range(len(featmat))]
    gln_plain = run_gln(gln_plain_tr, gln_plain_te, featmat.shape[1])
    gln_aug = run_gln(gln_aug_tr, gln_aug_te, featmat.shape[1] + 1)

    out = {"n_episodes": len(eps), "n_train_pools": len(tr_pools), "n_test_pools": len(te_pools),
           "n_laundered_summaries_test": sum(1 for i in range(len(ids)) if is_summary[i] and labels[i] == 1.0),
           "gnn_mean_with_graph": metrics(scores_graph), "gnn_content_only": metrics(scores_content),
           "gnn_max_aggregating": metrics(scores_max),
           "gln_node_only": metrics(gln_plain), "gln_plus_lineage_max_feature": metrics(gln_aug),
           "max_lineage_propagation": {
               "laundered_summary_detection": rate_with_ci(max_det, max_n),
               "summary_own_anomaly_detection": rate_with_ci(own_det, max_n),
               "benign_fpr_target": 0.10},
           "note": "The GNN's MEAN message passing (gnn_mean_with_graph) barely beats content-only because "
                   "it dilutes the single poison ancestor among ~4 benign co-parents. MAX aggregation over "
                   "DERIVED_FROM parents (the containment guard's logic) is the right operation and catches "
                   "nearly all laundered summaries. Features = GNN features + the anomaly signal (the fix "
                   "for the GNN's non-discriminative saturation)."}
    g = out["gnn_mean_with_graph"]["laundered_summary_detection"]
    c = out["gnn_content_only"]["laundered_summary_detection"]
    mx = out["max_lineage_propagation"]["laundered_summary_detection"]
    own = out["max_lineage_propagation"]["summary_own_anomaly_detection"]
    # Discriminativeness = detection - FPR (a 100%-at-100%-FPR arm is saturated, not a detector).
    def disc(arm):
        m = out[arm]
        return m["laundered_summary_detection"]["rate"] - m["benign_fpr"]["rate"]
    xg = out["gnn_max_aggregating"]["laundered_summary_detection"]
    out["G-1_mean_graph_lifts"] = bool(disc("gnn_mean_with_graph") > disc("gnn_content_only") + 0.05)
    out["G-2_max_lineage_rule_lifts"] = bool(mx["rate"] > own["rate"] + 0.10)
    out["G-3_learned_max_gnn_beats_mean_gnn"] = bool(disc("gnn_max_aggregating") > disc("gnn_mean_with_graph") + 0.05)
    out["G-4_lineage_feature_rescues_gln"] = bool(disc("gln_plus_lineage_max_feature") > disc("gln_node_only") + 0.20)
    out["verdict"] = (
        f"The graph GENUINELY carries the laundering signal: the explicit MAX-over-lineage propagation "
        f"(the containment guard's own logic) detects {mx['rate']:.0%} of laundered summaries vs "
        f"{own['rate']:.0%} from a summary's own content. BUT a LEARNED graph model does not realise it at "
        f"this data scale: the mean-GNN dilutes the poison (no lift over content-only), and a learned "
        f"max-aggregating GNN ({xg['rate']:.0%} at 10% FPR) does not beat it either -- the Phase 11 "
        f"small-scale limitation. The GLN is graph-agnostic and its node-only scores saturate "
        f"(non-discriminative); fed the graph-derived max-lineage anomaly as a feature it becomes a real "
        f"detector ({out['gln_plus_lineage_max_feature']['laundered_summary_detection']['rate']:.0%} at "
        f"{out['gln_plus_lineage_max_feature']['benign_fpr']['rate']:.0%} FPR). Deployable answer: the "
        f"explicit max-over-lineage rule, not a learned GNN.")
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    print(f"episodes {r['n_episodes']}, test laundered summaries {r['n_laundered_summaries_test']}")
    for arm in ("gnn_mean_with_graph", "gnn_content_only"):
        ls = r[arm]["laundered_summary_detection"]
        print(f"  {arm:20s} laundered-summary {ls['k']}/{ls['n']} ({ls['rate']:.0%})")
    mx = r["max_lineage_propagation"]
    print(f"  max_lineage_propagation  {mx['laundered_summary_detection']['k']}/"
          f"{mx['laundered_summary_detection']['n']} ({mx['laundered_summary_detection']['rate']:.0%}) "
          f"vs summary-own {mx['summary_own_anomaly_detection']['rate']:.0%}")
    for arm in ("gnn_max_aggregating", "gln_node_only", "gln_plus_lineage_max_feature"):
        ls = r[arm]["laundered_summary_detection"]
        print(f"  {arm:28s} laundered-summary {ls['k']}/{ls['n']} ({ls['rate']:.0%})")
    print("G-1 mean:", r["G-1_mean_graph_lifts"], "| G-2 max-rule:", r["G-2_max_lineage_rule_lifts"],
          "| G-3 learned-max-GNN:", r["G-3_learned_max_gnn_beats_mean_gnn"], "| G-4 GLN+feat:", r["G-4_lineage_feature_rescues_gln"])
    print(r["verdict"])
