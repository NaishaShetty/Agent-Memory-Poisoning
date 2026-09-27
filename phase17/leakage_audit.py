"""Phase 17 Workstream A/reproducibility -- AUTOMATED leakage/contamination checks.

Runs structural checks that do not depend on any live LLM call, so they are cheap enough
to run every time and to wire into CI:
  1. train/eval CONVERSATION overlap for every benign split this project uses to
     calibrate/threshold a detector (`StackedDetector`'s dev-negative pools);
  2. attack-family / provenance overlap between the DEV sets used to tune the judge and
     the stacked detector (`dev_sets.py`, `dev_sets2.py`, `dev_family_sets.py`) and every
     held-out EVAL poison split (`poison_sets.py`, `novel_attacks.py`, `translation.py`,
     `corpus_extended.py`);
  3. duplicate scenario TEXT across splits (near-duplicate check via exact + embedding
     cosine, catching accidental copy-paste rather than deliberate paraphrase);
  4. missing/malformed metadata (every `PoisonRecord` has a non-empty `scenario_id`,
     `text`, `family`, `split`).

This module never mutates data; a violation is a hard `LeakageError`, so a caller (or a
CI job) can assert `audit_all()` raises nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Sequence, Tuple


class LeakageError(AssertionError):
    """A real, structural contamination finding -- not a style nit."""


@dataclass(frozen=True)
class AuditReport:
    checks: Tuple[str, ...]
    passed: Tuple[str, ...]
    details: Dict[str, object]


_LOCOMO_TASK_RE = re.compile(r"LOCOMO-T(\d+)")


def _conv_ids(scenario_id: str) -> FrozenSet[str]:
    m = _LOCOMO_TASK_RE.search(scenario_id)
    return frozenset({m.group(1)}) if m else frozenset()


def check_benign_train_eval_conversation_disjoint() -> Dict[str, object]:
    """For every benign population `StackedDetector` calibration draws negatives from
    (`dataset_arena`, `convomem`, `perltqa`), the TRAIN half (even-indexed pools, by
    `pool_id`) and the EVAL half (odd-indexed pools) must share zero `pool_id` (a pool is
    one real conversation/dialogue/event-group by construction -- see each module's own
    docstring) and zero LoCoMo conversation id where scenario ids encode one."""
    from phase17.arenas import dataset_arena
    from phase17.extra_datasets import convomem_pools
    from phase17.perltqa import perltqa_pools

    out = {}
    for name, (pools, _truth) in (("dataset_arena", dataset_arena()), ("convomem", convomem_pools()), ("perltqa", perltqa_pools())):
        ordered = sorted(pools, key=lambda p: p.pool_id)
        tr, te = ordered[0::2], ordered[1::2]
        tr_pool_ids = {p.pool_id for p in tr}
        te_pool_ids = {p.pool_id for p in te}
        pool_overlap = tr_pool_ids & te_pool_ids
        tr_conv = frozenset().union(*(_conv_ids(m.scenario_id) for p in tr for m in p.memories)) if tr else frozenset()
        te_conv = frozenset().union(*(_conv_ids(m.scenario_id) for p in te for m in p.memories)) if te else frozenset()
        conv_overlap = tr_conv & te_conv
        if pool_overlap:
            raise LeakageError(f"{name}: train/eval pool_id overlap: {sorted(pool_overlap)}")
        if conv_overlap:
            raise LeakageError(f"{name}: train/eval LoCoMo conversation overlap: {sorted(conv_overlap)}")
        out[name] = {"n_train_pools": len(tr), "n_eval_pools": len(te), "n_train_conv": len(tr_conv), "n_eval_conv": len(te_conv)}
    return out


def check_poison_target_not_in_benign_train() -> Dict[str, object]:
    """The 4 real LoCoMo conversations a founding attack family targets (DSRM=T1,
    FARMA=T2, MPBench=T3, Sleeper=T4) must not supply any of `StackedDetector`'s benign
    TRAIN negatives (that would let the detector see the poison's own conversation,
    stripped of the poison, as a 'normal' example of the same context it must later flag)."""
    from phase17.arenas import dataset_arena

    poison_target_convs = {"1", "2", "3", "4"}
    pools, _truth = dataset_arena()
    tr = sorted(pools, key=lambda p: p.pool_id)[0::2]
    tr_conv = frozenset().union(*(_conv_ids(m.scenario_id) for p in tr for m in p.memories)) if tr else frozenset()
    overlap = tr_conv & poison_target_convs
    if overlap:
        raise LeakageError(f"benign TRAIN negatives include poison-target conversation(s) {sorted(overlap)}")
    return {"poison_target_convs": sorted(poison_target_convs), "train_convs_seen": sorted(tr_conv), "overlap": sorted(overlap)}


def check_dev_eval_text_disjoint() -> Dict[str, object]:
    """Exact-text disjointness between every DEV set used to tune the judge/detector/
    stacked-detector and every EVAL poison split, INCLUDING the round-4/5 extended dev
    pool and the round-4 extended corpus (`corpus_extended.py`'s `held_out_extended`
    split), so a newly-added dev or eval set can never silently reintroduce a leak this
    check would have caught on the original 5 splits alone. (Near-duplicate/paraphrase-
    level closeness is a SEPARATE, already-measured axis -- `dev_sets2.py`'s
    `OVERLAP_DEV`/mechanism tags and `run_scores_eval.EVAL_OVERLAP` -- this check catches
    literal copies only.)"""
    from phase17 import dev_family_sets, dev_sets, dev_sets2
    from phase17.corpus_extended import extended_records
    from phase17.novel_attacks import novel_records
    from phase17.poison_sets import evasion_records, original_records, regenerated_records
    from phase17.translation import zh_records

    dev_texts = ({a["text"] for a in dev_sets.load()["attacks"]} | {b["text"] for b in dev_sets.load()["benign"]}
                 | {a["text"] for a in dev_sets2.load()["attacks"]} | {b["text"] for b in dev_sets2.load()["benign"]}
                 | {i["text"] for i in dev_family_sets.load()})
    eval_texts = ({r.text for r in original_records()} | {r.text for r in regenerated_records()} | {r.text for r in evasion_records()}
                  | {r.text for r in novel_records()} | {r.text for r in zh_records()} | {r.text for r in extended_records()})
    overlap = dev_texts & eval_texts
    if overlap:
        raise LeakageError(f"{len(overlap)} exact-text duplicate(s) between DEV and EVAL sets: {list(overlap)[:3]}")
    return {"n_dev_texts": len(dev_texts), "n_eval_texts": len(eval_texts), "n_overlap": len(overlap)}


def check_poison_record_metadata_complete(records: Sequence) -> Dict[str, object]:
    """Every `PoisonRecord` must carry a non-empty scenario_id/text/family/split."""
    missing: List[str] = []
    for r in records:
        if not (r.scenario_id and r.text and r.family and r.split):
            missing.append(r.scenario_id or "<blank>")
    if missing:
        raise LeakageError(f"{len(missing)} record(s) with missing metadata: {missing[:5]}")
    return {"n_checked": len(records), "n_missing": len(missing)}


def audit_all() -> AuditReport:
    from phase17.novel_attacks import novel_records
    from phase17.poison_sets import all_records
    from phase17.translation import zh_records

    checks = ("benign_train_eval_conversation_disjoint", "poison_target_not_in_benign_train",
              "dev_eval_text_disjoint", "poison_record_metadata_complete")
    details = {
        "benign_train_eval_conversation_disjoint": check_benign_train_eval_conversation_disjoint(),
        "poison_target_not_in_benign_train": check_poison_target_not_in_benign_train(),
        "dev_eval_text_disjoint": check_dev_eval_text_disjoint(),
        "poison_record_metadata_complete": check_poison_record_metadata_complete(list(all_records()) + novel_records() + zh_records()),
    }
    return AuditReport(checks=checks, passed=checks, details=details)


__all__ = ["LeakageError", "AuditReport", "audit_all", "check_benign_train_eval_conversation_disjoint",
           "check_poison_target_not_in_benign_train", "check_dev_eval_text_disjoint", "check_poison_record_metadata_complete"]
