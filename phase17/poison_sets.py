"""Phase 17 -- the provenance-tagged poison populations that address the two
real constraints `docs/phase17/PHASE17_PLAN.md` Section 3 names.

CONSTRAINT (a), thin statistical power: Phase 12's poison set is 15 records
(one record = 6.7 detection points). This module assembles a much larger real
population -- the original 15 + the 9 real `regenerate_poison_batch()` records
+ recorded LLM evasion variants of all 24 -- and every downstream number is
reported with counts, Wilson intervals and paired exact tests (`stats.py`),
never as a bare percentage.

CONSTRAINT (b), in-sample contamination: several admission signals were
written from the SAME original Track B instances that also form the
evaluation poison. Every record therefore carries a `split`:
- `signal_source`   -- the original 15 (signals were built/tuned from these;
                       results on them are IN-SAMPLE and reported as such);
- `held_out_regen`  -- the 9 real regenerated records: same mechanisms, new
                       real LoCoMo targets, produced by Phase 11 Track B
                       BEFORE Phase 14's signals 12-14 existed and never used
                       to tune any signal -- held out;
- `held_out_evasion`-- LLM-rewritten variants (`evasion.py`), held out by
                       construction and adversarially adapted.
Nothing here is hand-written attack content.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from phase11.data.poison_regeneration import regenerate_poison_batch
from phase11.data.real_corpus import real_poison_scenarios
from phase6.defense.orchestration.pipeline import MemoryScenario, ScenarioPool

SPLIT_SOURCE = "signal_source"
SPLIT_REGEN = "held_out_regen"
SPLIT_EVASION = "held_out_evasion"
EVASION_CACHE = Path(__file__).parent / "data" / "evasion_variants.json"


@dataclass(frozen=True)
class PoisonRecord:
    scenario_id: str
    text: str
    family: str
    split: str
    parent_id: Optional[str] = None
    variant: Optional[str] = None


def original_records() -> List[PoisonRecord]:
    return [PoisonRecord(m.scenario_id, m.content_text, m.attack_family_ground_truth, SPLIT_SOURCE)
            for m in real_poison_scenarios().memories]


def regenerated_records() -> List[PoisonRecord]:
    pool, _ = regenerate_poison_batch()
    return [PoisonRecord(m.scenario_id, m.content_text, m.attack_family_ground_truth, SPLIT_REGEN)
            for m in pool.memories]


def evasion_records(path: Path = EVASION_CACHE) -> List[PoisonRecord]:
    """Only VALID recorded variants (still similar to their parent, not a
    refusal); invalid ones stay in the cache for the report's accounting."""
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        PoisonRecord(v["variant_id"], v["text"], v["family"], SPLIT_EVASION, v["parent_id"], v["strategy"])
        for v in data["variants"] if v["valid"]
    ]


def all_records(include_evasion: bool = True) -> List[PoisonRecord]:
    recs = original_records() + regenerated_records()
    return recs + (evasion_records() if include_evasion else [])


def by_split(records: List[PoisonRecord]) -> Dict[str, List[PoisonRecord]]:
    out: Dict[str, List[PoisonRecord]] = {}
    for r in records:
        out.setdefault(r.split, []).append(r)
    return out


def as_pool(records: List[PoisonRecord], pool_id: str = "phase17-poison") -> ScenarioPool:
    return ScenarioPool(pool_id, tuple(
        MemoryScenario(r.scenario_id, r.text, is_poison_ground_truth=True, attack_family_ground_truth=r.family)
        for r in records))


__all__ = ["PoisonRecord", "SPLIT_SOURCE", "SPLIT_REGEN", "SPLIT_EVASION", "original_records",
           "regenerated_records", "evasion_records", "all_records", "by_split", "as_pool"]
