"""Phase 17 Workstream G -- explicit sanity/bound baselines. These are reference bounds,
never ranked as "better"/"worse" than a real defense: they exist so a reader can see
whether a detector's numbers are meaningfully different from trivial or budget-matched
behavior.

ALWAYS_ALLOW    -- detection 0%, FPR 0%, utility maximal. Identical to `CONFIG_B0_NO_DEFENSE`
                   already reported everywhere in this project; re-exposed here under its
                   bound name so it appears in the same table as the other two bounds.
ALWAYS_QUARANTINE -- detection 100%, FPR 100%, utility minimal (every memory excluded).
RANDOM_BUDGET_MATCHED -- flags/excludes memories UNIFORMLY AT RANDOM at the SAME rate a
                   real detector alerts at (its own flagged/excluded fraction on the same
                   population), so a reader can see whether that detector's detection is
                   attributable to more than "it alerts a lot." Seeded, reproducible.
"""

from __future__ import annotations

import random
from typing import Dict, Sequence

from phase17.stats import rate_with_ci


def always_allow(ids: Sequence[str]) -> Dict[str, bool]:
    return {i: False for i in ids}


def always_quarantine(ids: Sequence[str]) -> Dict[str, bool]:
    return {i: True for i in ids}


def random_budget_matched(ids: Sequence[str], alert_rate: float, seed: int = 17) -> Dict[str, bool]:
    """Flags exactly `round(alert_rate * len(ids))` of `ids`, chosen uniformly at random
    (no information about content or ground truth), reproducibly."""
    rng = random.Random(seed)
    n = len(ids)
    k = round(alert_rate * n)
    chosen = set(rng.sample(list(ids), min(k, n)))
    return {i: (i in chosen) for i in ids}


def compare_to_random(poison_ids: Sequence[str], benign_ids: Sequence[str], detector_flags: Dict[str, bool], n_boot: int = 200, seed: int = 17) -> dict:
    """Detection/FPR for `detector_flags` vs `n_boot` random-budget-matched draws at the
    SAME overall alert rate, over the SAME population. Reports the random baseline's mean
    and 95% range so a detector's real detection can be read against chance."""
    all_ids = list(poison_ids) + list(benign_ids)
    alert_rate = sum(detector_flags.get(i, False) for i in all_ids) / len(all_ids) if all_ids else 0.0
    real_det = rate_with_ci(sum(detector_flags.get(i, False) for i in poison_ids), len(poison_ids)) if poison_ids else None
    real_fpr = rate_with_ci(sum(detector_flags.get(i, False) for i in benign_ids), len(benign_ids)) if benign_ids else None
    rng = random.Random(seed)
    rand_dets = []
    for b in range(n_boot):
        rb = random_budget_matched(all_ids, alert_rate, seed=rng.randrange(1 << 30))
        rand_dets.append(sum(rb[i] for i in poison_ids) / len(poison_ids) if poison_ids else 0.0)
    rand_dets.sort()
    return {"alert_rate_matched": alert_rate, "real_detection": real_det, "real_fpr": real_fpr,
            "random_detection_mean": sum(rand_dets) / len(rand_dets) if rand_dets else 0.0,
            "random_detection_95range": (rand_dets[int(0.025 * n_boot)], rand_dets[int(0.975 * n_boot) - 1]) if rand_dets else (0.0, 0.0)}


__all__ = ["always_allow", "always_quarantine", "random_budget_matched", "compare_to_random"]
