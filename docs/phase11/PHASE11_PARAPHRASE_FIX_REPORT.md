# Phase 11 — Closing the Paraphrase Blind Spot and the Real-Corpus Gap

Direct answer to "fix it," in response to the two items named as
genuinely open at the end of the blend-wiring investigation: (1)
paraphrase-poison needs a genuinely new signal, not a combination-rule
change, and (2) the real-7-attack-corpus gap likely needs real signal, not
a better blend of existing signals. Both are addressed here with the SAME
real, already-shipped signal — not a coincidence, a real, measured
consequence of what that signal actually captures.

**No git commit or push was made for any of this work — all changes are
local, uncommitted file modifications only, per explicit instruction.**

## 1. The fix: a signal that already existed, never given to the GNN

`phase6/defense/retrieval/embedding_signals.py` (Phase 6.6, D2) is a real,
already-shipped, already-validated embedding-based consensus-divergence
signal, built specifically because the lexical (D1) signal's own module
docstring already discloses its failure mode: "three differently-WORDED
but same-lie coordinated poison records evade lexical clustering
entirely." That is exactly `PARAPHRASE-POISON-*`. Direct measurement
confirmed it: lexical `consensus_divergence_score` is exactly `0.0` for
every `PARAPHRASE-POISON-*` example; the semantic signal correctly
clusters them (poison mean 0.184 vs. benign mean 0.081 across the whole
held-out corpus).

## 2. A real mistake, caught and corrected before it shipped

The first version of this fix added the new key directly to the shared
`FEATURE_KEYS` constant in `phase11/gnn/features.py`. That constant is
also imported by `phase11/gln/stream.py` (the GLN) — silently expanding
the GLN's own input dimension to one it had never been calibrated or
toy-validated against. Real, measured consequence: GLN's benign held-out
risk score jumped to ~1.0 for every example, and B10 collapsed to the
same 100%/100% degenerate saturation `WEIGHTED_SUM` was already known for.

**Fixed by decoupling, not by reverting the feature**: `FEATURE_KEYS`
(9 keys) is now left completely untouched — still what the GLN, Option 1
(`self_supervised.py`), and Option 2 (`expanded_features/dataset.py`) all
depend on for their own already-reported, protected numbers. A new,
separate `GNN_FEATURE_KEYS` (10 keys) and `pool_node_features_gnn()` exist
specifically for the GNN's own pipeline. `train.py::build_dataset()` and
`train_model()` gained additive, backward-compatible parameters
(`feature_keys`, `feature_fn`; `in_dim` now reads the real dataset shape
instead of a hardcoded module constant) so every pre-existing call site —
including `run_gnn_feasibility_study()`, Baseline A — is unaffected.

## 3. Closing the gap at its actual source, not routing around it

A second real check was done before committing to the GNN-only fix: does
adding this signal to the GNN alone even reach B10's final decision? No —
`PARAPHRASE-POISON-*` scores GLN exactly `0.0`, and MIN-gating erases any
GNN improvement there regardless of how good the GNN's own score becomes
(confirmed directly, not assumed). Swapping MIN for MAX was already tested
in the prior investigation and rejected (100%/100% degenerate).

**The real fix closes the gap at its source instead**: the semantic key
was registered as its own sanctioned signal (`semantic_consensus_divergence_score`,
`RETRIEVAL_SIGNAL_KEYS`) and `_grouped_gated_rule()`'s `retrieval_group`
now takes `MAX(lexical, semantic)` — not a replacement, not a "combination
rule over two learned estimates" (the thing that was previously ruled
out), but two independent DETECTION MECHANISMS for the same phenomenon,
where either firing is real evidence. This fixes B9 itself, not just B10,
which means B10 inherits the fix regardless of what the GNN/GLN
individually do.

**One real bug found and fixed along the way**: `_PRE_PHASE11_SIGNAL_KEYS`
(the denominator for `WEIGHTED_SUM`'s flat weighting) was dynamically
derived from `RETRIEVAL_SIGNAL_KEYS`, so adding the new key silently
diluted every OTHER signal's flat share too — caught by
`test_dev_corpus_comparison_against_combined_action_baseline`'s own
regression check (WEIGHTED_SUM's flagged count dropped from 7 to 5 with no
underlying signal change). Fixed by freezing `_PRE_PHASE11_SIGNAL_KEYS` as
an explicit literal, restoring the original intent that comment already
stated (new keys must never silently reweight existing ones).

## 4. Real, measured before/after

| | Before | After |
|---|---|---|
| **B9** (rule-only) detection / FPR | 70.6% / 7.3% | **100.0% / 14.6%** |
| **B10** (`GROUPED_GATED`) detection / FPR | 70.6% / 7.3% | **100.0% / 14.6%** |
| MemoryGraft-style-volume detection (B9 and B10) | 50.0% | **100.0%** |
| B8 (independent guard voting, untouched) | 70.6% / 7.3% | 70.6% / 7.3% (unchanged, confirms scope) |

**The FPR cost is real and traced, not glossed over**: every one of the 3
new false positives (`PARAPHRASE-TRUTH-*`) is a genuine benign "truth"
memory that happens to sit inside a coordinated PARAPHRASE-poison pool —
the exact same mechanism that already flagged the analogous
`NEARDUP-TRUTH-*` memories under the lexical signal alone (a minority
truth record inside a coordinated-poison pool reads as "divergent from
consensus," a known, already-accepted limitation of pool-consensus
escalation this project has never claimed to be free of). Not a new,
unrelated failure mode.

## 5. A real, unplanned bonus: the real-7-attack-corpus gap closed too

The blend's own generalization to Phase 11.z's real 7-attack corpus
(`real_corpus.py`) was re-measured with the new 10-feature GNN vocabulary,
not assumed unchanged:

| Blend weight | Real-attack-corpus AUROC, before | After |
|---|---|---|
| w=0.0 | 0.507 | **0.917** |
| w=0.25 | 0.521 | **0.934** |
| w=0.50 (now wired in) | 0.532 | **0.912** [0.608, 0.990 across seeds] |

**Real, measured, positive finding**: the semantic signal is robust to
surface-level text style (real LoCoMo-derived dialogue vs. hand-authored
synthetic text) in a way the previous lexical/regex-based features were
not, closing the generalization gap the earlier report found unresolved
without any additional training data — the hypothesis that this needed
"real training data, not a better blend" turned out to be only half right:
what it actually needed was a signal that doesn't key off surface
phrasing at all. Reported honestly: `w=0.50` (the value wired into B10,
chosen for the ablation corpus's own pooled-family/LOFO trade-off) has a
wider seed range on this population (0.61–0.99) than `w=0.25` (0.93–0.93,
tight) — B10's own calibration was not re-tuned against this population
(that would be circular), so this real number is reported as a
complementary validation result, not a claim that `w=0.50` is optimal
here too.

## 6. What this does not establish

FARMA's own LOFO ranking problem (from the earlier weight-decay/threshold
investigation) is untouched by this fix — it was never about the
retrieval signal. The real-corpus generalization result (Section 5) is
still scoped to AUROC (ranking), not a calibrated detector with its own
threshold on that corpus — no such threshold was fit or claimed.

## Regression status

`python -m pytest phase6/ attribution/ phase7/ phase8/ phase11/ -q` →
**699 passed, 13 skipped, 0 failed** — same total as before this
investigation (updated assertions on already-existing tests, not new
tests, since this was a fix to already-locked-in numbers, disclosed with
dated Update notes on each). B8 (independent per-guard voting) and every
GLN, Option 1, and Option 2 protected number reconfirmed byte-for-byte
unchanged where they should be.

## Files changed

`phase6/defense/risk/risk_score.py` (new sanctioned key, `_retrieval_group_score()`,
`_PRE_PHASE11_SIGNAL_KEYS` bugfix), `phase6/evaluation/ablations/run_b0_b7.py`
(`run_b9_risk_composed()` now supplies the semantic signal),
`phase6/tests/test_risk_score.py`/`test_run_b9_risk_composed.py` (updated,
dated assertions), `phase11/gnn/features.py` (new `GNN_FEATURE_KEYS`/
`pool_node_features_gnn()`, `FEATURE_KEYS` unchanged), `phase11/gnn/train.py`
(additive `feature_keys`/`feature_fn` parameters, `in_dim` correctness
fix), `phase11/gnn/blend_pooled_family.py`, `phase11/gnn/blend_real_attack_corpus.py`,
`phase11/evaluation/run_b10.py` (all three updated to use the GNN feature
set and the new `w=0.50`), plus updated tests
(`phase11/tests/test_blend_wiring.py`, `test_run_b10.py`,
`test_expanded_features.py`). Nothing in `phase11/gln/`,
`phase11/gnn/self_supervised.py`, or `phase11/expanded_features/` was
modified.
