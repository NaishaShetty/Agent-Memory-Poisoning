"""v7 Gap 2 recovery after rewrite: DCR (distinctive-claim reconciliation). Pre-registered SA7_PREREGISTRATION.md §3.

Before matching a rewritten memory q to the store's logged tainted outputs, drop each sentence of q that RAR-S-matches
any of the owner's own pre-existing store memories (leave-one-out when q is itself a store memory); match only the
remaining sentences (RAR-S, sentence level) against the logged tainted outputs. Candidate pre-filter: the TOPN most
similar candidates by sem with sem >= floor (as v6 reconciliation).

`dev()` runs the pre-registered gate on HO9 (v7 development): carried to HO10 only if false association <= 5% (owner
store and unflagged benign descendants) and recovery >= 90% of correct roots.
"""
from __future__ import annotations

from phase17.defence_v7 import atomic  # noqa: F401  (crash-safe checkpoints: atomic file writes)

import json
from pathlib import Path
from typing import Dict, List

import numpy as np

from phase17.defence_v7.g2_dev import FLOOR, NLI7, TAU_N, TAU_R, sents

DATA = Path(__file__).resolve().parents[1] / "data" / "defence_v7"
TOPN = 10


class SentMatcher:
    """Sentence-level RAR-S matching with an embedding cache and the v7 NLI cache (never v6's)."""

    def __init__(self, F):
        self.F = F
        self.nli = json.loads(NLI7.read_text(encoding="utf-8")) if NLI7.exists() else {}
        self._todo = []

    def _pairs_ok(self, a: str, b: str) -> bool:
        from phase17.defence_v3.ctc import nli_entail

        if self.F.sem(a, b) < FLOOR:
            return False
        nli_entail([(a, b), (b, a)], self.nli, path=None)
        return self.nli[f"{a}||{b}"] >= TAU_N or self.nli[f"{b}||{a}"] >= TAU_R

    def sentence_matches(self, s: str, cands: List[str]) -> List[int]:
        """Indices of candidate TEXTS that some sentence-pair (s, candidate sentence) RAR-S-matches."""
        from phase17.defence_v6.fpb import exact

        if not cands:
            return []
        self.F.embed([s] + cands)
        sims = np.array([self.F.emb[c] for c in cands]) @ self.F.emb[s]
        out = []
        for i in np.argsort(-sims)[:TOPN]:
            if sims[i] < FLOOR:
                break
            c = cands[i]
            cs = sents(c)
            self.F.embed(cs)
            if exact(s, c) or any(self._pairs_ok(s, t) for t in cs):
                out.append(int(i))
        return out

    def save(self):
        NLI7.write_text(json.dumps(self.nli), encoding="utf-8")


def residual(M: SentMatcher, q: str, owner_store: List[str], exclude: str = None) -> List[str]:
    base = [t for t in owner_store if t != exclude]
    return [s for s in sents(q) if not M.sentence_matches(s, base)]


def dcr(M: SentMatcher, q: str, owner_store: List[str], logged: List[str], exclude: str = None) -> List[int]:
    hits = set()
    for s in residual(M, q, owner_store, exclude):
        hits |= set(M.sentence_matches(s, logged))
    return sorted(hits)


def evaluate_rows(rs, M: SentMatcher, store: Dict[int, List[str]]) -> Dict:
    from phase17.defence_v6.fpb import canon
    from phase17.defence_v6.ledger import sha
    from phase17.stats import rate_with_ci

    owners = sorted({r["owner"] for r in rs})
    A = [r for r in rs if r["kind"] == "atk" and r["flagged"]]
    BU = [r for r in rs if r["kind"] == "ben_unflagged"]
    flagged = [r for r in rs if r["flagged"]]
    log = {o: [(sha(canon(g)), g, r["key"], r["root"]) for r in flagged if r["owner"] == o for g in r["gens"]] for o in owners}
    rec, wh = [], []
    for n, r in enumerate(A):
        L = log[r["owner"]]
        hits = dcr(M, r["rw"][3], store[r["owner"]], [g for _, g, _, _ in L])
        keys = {L[i][2] for i in hits}
        rec.append(r["key"] in keys)
        cand_roots = {L[i][3] for i in hits}
        wh.append(any(any(M.sentence_matches(s, [rt]) for s in sents(r["rw"][3])) for rt in cand_roots))
        if n % 25 == 0:
            M.save()
            print(f"  DCR attacks {n}/{len(A)}", flush=True)
    fa_store = []
    for o in owners:
        L = [g for _, g, _, _ in log[o]]
        for t in store[o]:
            fa_store.append(bool(dcr(M, t, store[o], L, exclude=t)))
        M.save()
        print(f"  DCR owner {o} store done", flush=True)
    fa_bu = [bool(dcr(M, r["rw"][k], store[r["owner"]], [g for _, g, _, _ in log[r["owner"]]])) for r in BU for k in range(4)]
    M.save()
    carry_rw4 = [i for i, r in enumerate(A) if r["carry_rw"][3]]
    return {"recovery_correct_g4": rate_with_ci(sum(rec), len(rec)),
            "withheld_carrying_g4(carry judged on rewritten text)": rate_with_ci(sum(wh[i] for i in carry_rw4), len(carry_rw4)),
            "false_association_owner_store": rate_with_ci(sum(fa_store), len(fa_store)),
            "false_association_unflagged_benign_desc": rate_with_ci(sum(fa_bu), len(fa_bu))}


def dev() -> Dict:
    from phase17 import harm_study_v2 as H
    from phase17.defence_v6 import g2_eval as G

    F = G.Feat()
    rs = G.rows(F)                          # HO9; v6 caches read only
    M = SentMatcher(F)
    store = {o: [t for _, t in H._store_for(o)] for o in sorted({r["owner"] for r in rs})}
    res = evaluate_rows(rs, M, store)
    rc = res["recovery_correct_g4"]["rate"] or 0
    fa = max(res["false_association_owner_store"]["rate"] or 0, res["false_association_unflagged_benign_desc"]["rate"] or 0)
    out = {"substrate": "HO9 (v7 development)", "C2_DCR": res,
           "gate": {"recovery>=90%": rc >= 0.90, "false_association<=5%": fa <= 0.05}}
    out["gate"]["carried_to_HO10"] = all(out["gate"].values())
    (DATA / "dcr_dev.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(json.dumps(dev(), indent=1))
