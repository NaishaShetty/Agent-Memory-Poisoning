"""Phase 17 Workstream E -- adaptive / defense-aware attacker, made explicit.

`evasion.py`'s LLM-rewritten variants of the 24 signal_source/regen poison records ARE
already this workstream's experiment (paraphrase surface features while preserving the
underlying manipulation objective), but Phase 17's earlier sections never verified the
SECOND half of the workstream's requirement: that the paraphrased variant still achieves
the ORIGINAL attack's objective, not just that it reads differently. A defense-aware
paraphrase that also destroys the lie is not evidence the defense was evaded -- it is
evidence the attacker broke their own attack.

This module checks, for every evasion variant, that it still asserts a claim
semantically equivalent to its parent's forged claim (via the same NLI entailment check
Phase 3 already uses for answer correctness -- reused verbatim, not reimplemented): the
variant's text must ENTAIL (or be entailed by) the parent's own forged content. Variants
that fail this check are EXCLUDED from "successful evasion" claims and reported
separately, never silently kept in the numerator.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from phase17.poison_sets import PoisonRecord, evasion_records, original_records, regenerated_records
from phase17.stats import rate_with_ci

OUT = Path(__file__).parent / "data" / "adaptive_attacker_objective_check.json"


def _objective_preserved(parent_text: str, variant_text: str) -> bool:
    from phase3.evaluation.agent.nli_entailment_correctness import check_entailment_equivalence

    return bool(check_entailment_equivalence(parent_text, variant_text, None)["is_equivalent"])


def run() -> dict:
    parents: Dict[str, PoisonRecord] = {r.scenario_id: r for r in original_records() + regenerated_records()}
    ev = evasion_records()
    rows: List[dict] = []
    for r in ev:
        parent = parents.get(r.parent_id)
        if parent is None:
            continue
        rows.append({"id": r.scenario_id, "parent_id": r.parent_id, "variant": r.variant, "family": r.family,
                     "objective_preserved": _objective_preserved(parent.text, r.text)})
    n_preserved = sum(row["objective_preserved"] for row in rows)
    by_variant: Dict[str, dict] = {}
    for v in sorted({row["variant"] for row in rows}):
        rs = [row for row in rows if row["variant"] == v]
        by_variant[v] = rate_with_ci(sum(row["objective_preserved"] for row in rs), len(rs))
    result = {"n_variants": len(rows), "objective_preserved": rate_with_ci(n_preserved, len(rows)), "by_variant": by_variant,
              "not_preserved_ids": [row["id"] for row in rows if not row["objective_preserved"]],
              "note": "'objective_preserved'=False means the paraphrase itself destroyed the forged claim (a broken "
                      "attack, not an evasion of the defense); those ids must be excluded from evasion-success claims."}
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    r = run()
    print(r["objective_preserved"], r["by_variant"], "not_preserved:", r["not_preserved_ids"])
    print("DONE")
