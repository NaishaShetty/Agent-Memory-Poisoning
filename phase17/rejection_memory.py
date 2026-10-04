"""REJECTION MEMORY: give the defense the one thing the adaptive attacker relies on it not having.

THE DIAGNOSIS. Against a single fixed poison, B13/B14/B15 exclude most attacks. Against the
query-based adaptive attacker (`adaptive_query_attacker.py`) they lose ~20% of the instances
they initially excluded: the attacker queries the live defense, reads its action, asks a model
to rewrite the note preserving the claim, and tries again, up to five times. Every published
config here is STATELESS -- each candidate is scored on its own text -- so five rewrites are
five independent attempts at a probabilistic detector, and the attacker needs only one to land.
At a per-attempt miss rate p, five attempts succeed with probability 1-(1-p)^5, which is why a
detector that is individually strong still bleeds ~20% under a budget of five.

But a real deployment is not stateless. The four rejected paraphrases HAPPENED. The defense saw
them, acted on them, and then threw the fact away. That discard is the vulnerability -- not the
detector's per-item accuracy, which is why making the detector marginally better (B14's 170x
cost) barely moves the adaptive number.

THE MECHANISM, deliberately small. When a candidate is hard-mitigated (QUARANTINE/BLOCK), store
its embedding in a per-scope ledger. A later candidate whose cosine similarity to any ledger
entry is >= REJECT_SIM is excluded on that basis alone, whatever its own content score says.
A claim-preserving paraphrase is, by construction, semantically close to what it paraphrases --
so the property the attacker must maintain to keep winning (the claim survives) is the same
property that gets them caught. Evading this needs a rewrite far enough from all previous
attempts to clear the radius, which the NLI claim-preservation check then fails. That is the
point: it converts the attacker's retry budget from an advantage into an accumulating liability.

WHAT IT COSTS, and this is the part that decides whether it is real. Two risks, both measured
in `eval_rejection_memory.py` rather than argued:
  1. A benign memory can land near a rejected one and be excluded for its neighbour's sins.
     Bounded by the radius, by per-scope isolation (one user's ledger never judges another's
     memories), and measured on every benign population.
  2. An attacker could poison the ledger itself -- deliberately getting innocuous-looking text
     rejected so that legitimate memories near it are blocked afterwards. This is a real
     denial-of-service surface and it is why entries EXPIRE (TTL) and why the ledger is capped.

THE THREAT MODEL, stated plainly because it bounds the claim. This helps only when the
attacker's attempts reach the same scope's ledger: the query-based adaptive attacker, which is
exactly the threat model it is built for. It does NOTHING against a single-shot attack, and
nothing against an attacker who distributes attempts across isolated scopes or waits out the
TTL. So B16's static recall is B15's by construction -- the ledger is empty on a first
attempt -- and the only numbers that should move are adaptive evasion and benign FPR. Any
report claiming this improves static detection is reading a bug.

Thresholds are fitted on DEV data only (`fit_threshold`) and the configuration frozen before
the hold-outs are touched, per the governing rule of the external reviews.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

CONFIG = Path(__file__).parent / "data" / "rejection_memory_config.json"

# Fitted on dev data only; see `fit_threshold()` and the frozen record in CONFIG.
REJECT_SIM = 0.97  # fitted on dev; see data/rejection_memory_config.json
TTL_SECONDS = 7 * 24 * 3600.0
MAX_ENTRIES = 256


def _embed(texts: Sequence[str]) -> np.ndarray:
    """Reuses the project's existing frozen bge-small encoder -- not a new model, so this adds
    no model to load and no cost beyond one forward pass per candidate."""
    from phase17.semantic_detector import _embed as embed

    return embed(list(texts))


@dataclass
class _Entry:
    vec: np.ndarray
    text: str
    at: float
    action: str


@dataclass
class RejectionLedger:
    """Per-scope memory of what was already rejected. A 'scope' is whatever isolation boundary
    the deployment has -- one user, one agent, one session. Cross-scope sharing would make the
    poisoning risk in the module docstring far worse for a marginal detection gain, so the
    default is strict per-scope isolation."""

    reject_sim: float = REJECT_SIM
    ttl: float = TTL_SECONDS
    max_entries: int = MAX_ENTRIES
    _by_scope: Dict[str, List[_Entry]] = field(default_factory=dict)

    def _live(self, scope: str, now: float) -> List[_Entry]:
        es = [e for e in self._by_scope.get(scope, ()) if now - e.at <= self.ttl]
        self._by_scope[scope] = es
        return es

    def observe(self, text: str, action: str, scope: str = "default", now: Optional[float] = None) -> None:
        """Record a hard mitigation. Non-excluding actions are NOT recorded: a FLAG means the
        defense was unsure, and building a blocking radius out of uncertainty is how a
        false-positive cascade starts."""
        from phase14.defended_retrieval import HARD_MITIGATION_ACTIONS

        if action not in HARD_MITIGATION_ACTIONS:
            return
        now = time.time() if now is None else now
        es = self._live(scope, now)
        es.append(_Entry(_embed([text])[0], text[:400], now, action))
        if len(es) > self.max_entries:
            del es[: len(es) - self.max_entries]

    def check(self, text: str, scope: str = "default", now: Optional[float] = None) -> Tuple[bool, float, str]:
        """(near a previous rejection, best similarity, the text it matched)."""
        now = time.time() if now is None else now
        es = self._live(scope, now)
        if not es:
            return False, 0.0, ""
        v = _embed([text])[0]
        sims = np.asarray([float(np.dot(v, e.vec)) for e in es])
        i = int(sims.argmax())
        return bool(sims[i] >= self.reject_sim), float(sims[i]), es[i].text

    def size(self, scope: str = "default") -> int:
        return len(self._live(scope, time.time()))

    def clear(self) -> None:
        self._by_scope.clear()


def fit_threshold(dev_benign, dev_paraphrase_pairs: Sequence[Tuple[str, str]],
                  max_benign_fpr: float = 0.005, max_poisoning_risk: float = 0.01) -> dict:
    """Choose REJECT_SIM on DEV data only.

    The trade-off is one-dimensional: how close may a NEW memory be to a REJECTED one before it
    is refused? Too tight and claim-preserving paraphrases slip through; too loose and
    legitimate memories get caught in the radius.

    MEASURING THE FALSE-POSITIVE SIDE CORRECTLY, which the first version of this function did
    not. It compared benign texts to OTHER BENIGN TEXTS and read off a 20.8% false-positive rate
    at sim>=0.86, which would have killed the idea. That number answers the wrong question: the
    ledger never contains benign text. It contains the attacks the defense hard-mitigated, so a
    benign memory is only ever at risk of matching a REJECTED POISON. Benign personal notes are
    mutually similar (same people, same handful of domains) in a way they are not similar to
    attack text, so the two measurements differ by an order of magnitude and only the second one
    describes the mechanism. The benign-to-benign curve is still computed and reported -- but as
    what it actually bounds, which is the ledger-poisoning blast radius (see `poisoning_risk`):
    IF an attacker manages to get innocuous text rejected, that is how much benign traffic sits
    inside its radius.

    So: FPR is max cosine from each benign text to the set of rejected poison texts; recall is
    cosine between a poison and its own claim-preserving paraphrase. The threshold is the lowest
    value holding FPR at or under `max_benign_fpr`, and we report the paraphrase recall that buys
    rather than picking the threshold to maximise it.
    """
    # `dev_benign` may be a {population: texts} mapping, and should be: a single pooled FPR
    # averages away the one population that matters. `legitimate_imperatives_40` is benign text
    # in the imperative voice attacks use, so it is the only benign population that sits near the
    # attack distribution at all -- a pooled 0% that hides a bad number there would be the same
    # mistake as reporting translated-Chinese attacks without the translation confound.
    if isinstance(dev_benign, dict):
        by_pop = {k: list(v) for k, v in dev_benign.items() if v}
    else:
        by_pop = {"pooled": list(dev_benign)}
    flat = [t for v in by_pop.values() for t in v]
    pairs = [(a, b) for a, b in dev_paraphrase_pairs if a and b]
    B = _embed(flat)
    A = _embed([a for a, _ in pairs])          # the originals: what lands in the ledger
    P = _embed([b for _, b in pairs])          # the attacker's claim-preserving rewrites

    # FPR side: each benign text against the whole ledger of rejected poisons.
    benign_vs_ledger = (B @ A.T).max(axis=1)
    # Recall side: a rewrite against its own parent.
    sim_p = np.asarray([float(np.dot(A[i], P[i])) for i in range(len(pairs))])
    # Blast-radius side: benign against benign, for the poisoning analysis only.
    sim_bb = B @ B.T
    np.fill_diagonal(sim_bb, -1.0)
    benign_vs_benign = sim_bb.max(axis=1)

    rows = []
    for thr in np.arange(0.70, 0.99, 0.01):
        rows.append({"thr": round(float(thr), 2),
                     "benign_fpr": round(float((benign_vs_ledger >= thr).mean()), 5),
                     "paraphrase_caught": round(float((sim_p >= thr).mean()), 4),
                     "poisoning_risk": round(float((benign_vs_benign >= thr).mean()), 5)})
    # Per-population FPR, so the hardest benign population is visible.
    emb_by_pop, i = {}, 0
    for k, v in by_pop.items():
        emb_by_pop[k] = (B[i:i + len(v)] @ A.T).max(axis=1)
        i += len(v)
    for r in rows:
        r["benign_fpr_by_population"] = {k: round(float((m >= r["thr"]).mean()), 5)
                                         for k, m in emb_by_pop.items()}
        r["worst_population_fpr"] = round(max(r["benign_fpr_by_population"].values(), default=0.0), 5)

    # THE BINDING CONSTRAINT IS NOT FALSE POSITIVES. Benign-to-rejected-poison similarity is
    # 0.0% at every threshold down to 0.70, so an FPR budget alone would select 0.70 -- far too
    # loose to defend, because at that radius one ledger-poisoned innocuous text would sit
    # within range of 65% of benign traffic. So the threshold is chosen by bounding the
    # POISONING blast radius as well, and that is what actually sets the value.
    ok = [r for r in rows
          if r["worst_population_fpr"] <= max_benign_fpr and r["poisoning_risk"] <= max_poisoning_risk]
    chosen = min(ok, key=lambda r: r["thr"]) if ok else rows[-1]
    out = {"chosen_reject_sim": chosen["thr"], "at_chosen": chosen, "max_benign_fpr": max_benign_fpr,
           "max_poisoning_risk": max_poisoning_risk,
           "selection_rule": ("lowest threshold holding WORST-POPULATION benign FPR <= "
                              f"{max_benign_fpr} AND ledger-poisoning blast radius <= "
                              f"{max_poisoning_risk}. The SECOND constraint is the binding one: "
                              "benign-to-rejected-poison similarity is 0.0% at every threshold "
                              "down to 0.70, so an FPR budget alone would have selected 0.70."),
           "n_dev_benign": len(flat), "n_benign_populations": len(by_pop), "n_dev_paraphrase_pairs": len(pairs), "curve": rows,
           "fitted_on": "DEV ONLY (benign dev populations + dev paraphrase pairs)",
           "fpr_definition": "max cosine from a benign memory to the set of REJECTED POISONS -- "
                             "what the ledger actually holds",
           "poisoning_risk_definition": "benign-to-benign nearest-neighbour rate: the share of "
                                        "benign traffic inside the radius of ONE successfully "
                                        "ledger-poisoned innocuous text. Bounded by TTL and the "
                                        "per-scope cap, not by this threshold.",
           "note": "frozen before either hold-out was touched; the hold-out numbers do not "
                   "re-tune this value"}
    CONFIG.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def configured_reject_sim() -> float:
    """The frozen fitted value if one exists, else the module default."""
    if CONFIG.exists():
        try:
            return float(json.loads(CONFIG.read_text(encoding="utf-8"))["chosen_reject_sim"])
        except Exception:
            pass
    return REJECT_SIM


if __name__ == "__main__":
    from phase17.eval_populations import benign_populations
    from phase17.poison_sets import evasion_records, original_records, regenerated_records

    benign = {k: list(v)[:200] for k, v in benign_populations().items()}
    parents = {r.scenario_id: r for r in original_records() + regenerated_records()}
    pairs = [(parents[r.parent_id].text, r.text) for r in evasion_records() if r.parent_id in parents]
    r = fit_threshold(benign, pairs)
    print(json.dumps({k: v for k, v in r.items() if k != "curve"}, indent=1))
    for row in r["curve"]:
        if 0.78 <= row["thr"] <= 0.96:
            print(f"  sim>={row['thr']:.2f}  benign_fpr {row['benign_fpr']:.3%}  "
                  f"paraphrase_caught {row['paraphrase_caught']:.1%}  "
                  f"(worst-pop fpr {row['worst_population_fpr']:.2%}, "
                  f"poisoning blast radius {row['poisoning_risk']:.1%})")
    print("DONE")
