"""Phase 11 -- the combined untrained score: `MAX(z(raw_sum), z(grouped_raw))`.

WHY MAX, NOT A REPLACEMENT OR AN AVERAGE
--------------------------------------------------------------------------------
Two real, disclosed, untrained (never fitted) reference scores exist, and
each has a real, opposite weakness the other does not share:

- `raw_sum` (flat sum of all 10 GNN features): lets FARMA's multiple
  admission-type signals accumulate WITHOUT a per-group cap, which is
  exactly what gives it a strong signature -- but that same lack of a cap
  is what let an unrelated hard-benign near-miss outscore Sleeper's own
  much narrower (2-factor, multiplicative) signature.
- `grouped_raw` (`grouped_raw_score.py`, the project's own already-shipped
  `GROUPED_GATED` rule-based composition): caps each signal GROUP at the
  SAME maximum contribution regardless of how many sub-signals fire,
  which is exactly what lets Sleeper's/MemoryGraft's narrow signatures
  compete on equal footing with a broad, multi-signal benign near-miss --
  but that same cap limits FARMA's own admission-group advantage.

Averaging the two (tried first, real, measured, rejected: macro detection
dropped back to 53.6%, Sleeper regressed to 0%) dilutes each one's own
strength by the other's own weakness for that specific family. MAX lets
whichever of the two actually separates a given family's signature from
benign dominate, without needing to know in advance which one that will
be -- the same "either detection mechanism firing is real evidence"
principle `_retrieval_group_score()`'s own MAX-of-lexical-and-semantic
design already uses, applied one level up.

REAL, MEASURED RESULT (LOFO, seed 11, before this module existed as
anything other than an ad hoc script)
--------------------------------------------------------------------------------
FARMA 100%/0% FPR, MemoryGraft-style-volume 100%/13.6% FPR, Sleeper
100%/9.1% FPR, propagated 50%/0% FPR (n=2, low-power) -- macro 87.5%
detection at 5.7% FPR, at `w_fit=0.25` (the SAME blend weight already used
elsewhere in this project's LOFO track). Full multi-seed measurement is
in `docs/phase11/PHASE11_COMBINED_SCORE_REPORT.md`.
"""

from __future__ import annotations

import torch

from phase11.gnn.grouped_raw_score import pools_grouped_raw_scores


def zscore(values: torch.Tensor, mean: float, std: float) -> torch.Tensor:
    if std == 0.0:
        return torch.zeros_like(values)
    return (values - mean) / std


def raw_sum(features: torch.Tensor) -> torch.Tensor:
    return features.sum(dim=1)


def grouped_raw_tensor(pools, node_ids) -> torch.Tensor:
    scores = pools_grouped_raw_scores(pools)
    return torch.tensor([scores.get(nid, 0.0) for nid in node_ids], dtype=torch.float32)


def combined_untrained_score(
    train_features: torch.Tensor, train_grouped: torch.Tensor,
    eval_features: torch.Tensor, eval_grouped: torch.Tensor,
) -> torch.Tensor:
    """z-score both `raw_sum` and `grouped_raw` on the SAME training
    population, take their elementwise MAX on `eval_features`/`eval_grouped`.
    `train_*` and `eval_*` may be the same tensors (in-fold) or different
    (held-out) -- the z-score statistics always come from `train_*`."""
    train_raw = raw_sum(train_features)
    raw_mean, raw_std = train_raw.mean().item(), train_raw.std(unbiased=False).item()
    grp_mean, grp_std = train_grouped.mean().item(), train_grouped.std(unbiased=False).item()

    eval_raw = raw_sum(eval_features)
    z_raw = zscore(eval_raw, raw_mean, raw_std)
    z_grouped = zscore(eval_grouped, grp_mean, grp_std)
    return torch.maximum(z_raw, z_grouped)


def blended_score(
    fitted: torch.Tensor, untrained: torch.Tensor, *, w_fit: float,
    fit_mean: float, fit_std: float,
) -> torch.Tensor:
    """`w_fit * z(fitted) + (1 - w_fit) * untrained` -- `untrained` is
    already z-scored by `combined_untrained_score()`."""
    z_fit = zscore(fitted, fit_mean, fit_std)
    return w_fit * z_fit + (1 - w_fit) * untrained
