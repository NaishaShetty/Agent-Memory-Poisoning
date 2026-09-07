"""Phase 3.3-DATASET -- assembles the per-(task, foundation) clean-agent behavioral
dataset record, per `PHASE3_CLEAN_DATASET_CONSTRUCTION_PLAN.md` section 3 (schema, as
approved, plus the user-requested addition: raw ledger/event references and everything
needed for later reconstruction).

Pure assembly only -- reads the already-produced result lists from
`campaign_formal_runner.py`'s `run_condition_a()`/`run_condition_gold_evidence()`/
`run_condition_b_mem0()`/`run_condition_c_amem()` (each a list of per-task dicts
carrying a Part-18 `trace` dict, per `trace.py`) and restructures them. Runs no LLM/
foundation calls itself, invents no ground truth, fabricates no field.

"Projection, not a second store" (the same principle `provenance_graph.py` and
`environment_record.py` were built on): this module never persists a copy of the
canonical/event ledgers -- every record carries only REFERENCES (`canonical_store_dir`,
`pool_key`, `config_fingerprint`) back to the real ledger directories a caller can open
with `build_provenance_graph()` on demand.
"""

from __future__ import annotations

from typing import Any, List, Mapping, MutableMapping, Optional, Sequence

FOUNDATION_MEM0 = "MEM0"
FOUNDATION_AMEM = "AMEM"


def _index_by_task_id(results: Sequence[Mapping[str, Any]]) -> Mapping[str, Mapping[str, Any]]:
    return {r["task_id"]: r for r in results}


def _condition_a_summary(result: Optional[Mapping[str, Any]]) -> Mapping[str, Any]:
    if result is None:
        return {"status": "NOT_RUN"}
    if result["status"] != "SUCCESSFUL_EVALUATION":
        return {"status": result["status"], "error": result.get("error")}
    t = result["trace"]
    return {
        "status": "SUCCESSFUL_EVALUATION",
        "answer": t["agent_output"],
        "evaluation_result": t["evaluation_result"],
        "failure_stage": t["failure_stage"],
        "fingerprints": t["fingerprints"],
    }


def _condition_gold_evidence_summary(result: Optional[Mapping[str, Any]]) -> Mapping[str, Any]:
    if result is None:
        return {"status": "NOT_RUN"}
    if result["status"] != "SUCCESSFUL_EVALUATION":
        return {"status": result["status"], "error": result.get("error")}
    t = result["trace"]
    return {
        "status": "SUCCESSFUL_EVALUATION",
        "answer": t["agent_output"],
        "evaluation_result": t["evaluation_result"],
        "failure_stage": t["failure_stage"],
        "fingerprints": t["fingerprints"],
        "evidence_items_used": result.get("evidence_items_used"),
        "missing_evidence_ids": result.get("missing_evidence_ids", []),
    }


def _condition_c_summary(result: Optional[Mapping[str, Any]]) -> Mapping[str, Any]:
    if result is None:
        return {"status": "NOT_RUN"}
    if result["status"] != "SUCCESSFUL_EVALUATION":
        return {"status": result["status"], "error": result.get("error")}
    t = result["trace"]
    return {
        "status": "SUCCESSFUL_EVALUATION",
        "answer": t["agent_output"],
        "evaluation_result": t["evaluation_result"],
        "failure_stage": t["failure_stage"],
        "fingerprints": t["fingerprints"],
        "retrieved_memory_ids": t["retrieved_memories"],
        "selected_memory_ids": t["selected_memories"],
        "exposed_memory_ids": t["exposed_memories"],
        "pool_key": result.get("pool_key"),
        "ingested_count": result.get("ingested_count"),
    }


def _raw_ledger_refs(dataset: str, campaign_id: str, foundation: str, result: Optional[Mapping[str, Any]]) -> Mapping[str, Any]:
    """References sufficient to reopen this record's REAL canonical ledgers via
    `canonical_wiring.canonical_store_dir_for_pool()` + `provenance_graph.
    build_provenance_graph()` -- never a copy of ledger contents. `None` fields are
    honest: Conditions A/GOLD_EVIDENCE structurally never touch a canonical ledger (no
    foundation is ever instantiated for them -- see `gold_evidence_runner.py`'s module
    docstring), so there is nothing to reference for those conditions, by construction.
    """
    if result is None or result.get("status") != "SUCCESSFUL_EVALUATION":
        return {
            "canonical_store_dir": None,
            "pool_key": None,
            "config_fingerprint": None,
            "canonical_event_report": None,
            "note": "Condition C did not succeed for this task; no ledger reference available.",
        }
    return {
        "campaign_id": campaign_id,
        "dataset": dataset,
        "foundation": foundation,
        "pool_key": result.get("pool_key"),
        "canonical_event_report": result.get("canonical_event_report"),
        "note": (
            "Reopen via canonical_wiring.canonical_store_dir_for_pool(experiments_dir, "
            "campaign_id, dataset, collection_name) -- collection_name is deterministic "
            "from (dataset, pool_key) per that function's own sha256 scheme, not stored "
            "here redundantly."
        ),
    }


def assemble_dataset_records(
    *,
    campaign_id: str,
    dataset: str,
    environment_record_id: Optional[str],
    results_a: Sequence[Mapping[str, Any]],
    results_gold_evidence: Sequence[Mapping[str, Any]],
    results_b_mem0: Sequence[Mapping[str, Any]],
    results_c_amem: Sequence[Mapping[str, Any]],
) -> List[MutableMapping[str, Any]]:
    """Build one record per (task_id, foundation) -- foundation in {MEM0, AMEM} -- per
    `PHASE3_CLEAN_DATASET_CONSTRUCTION_PLAN.md` section 3. Conditions A/B (no_memory,
    gold_evidence) are foundation-independent by construction and are therefore
    duplicated verbatim across a task's two records, exactly as the approved schema
    specifies -- never re-derived or diverging between them.

    A task missing from one or more result lists (e.g. an EXECUTION_FAILURE never
    retried) still produces a record -- the missing condition's block reports
    `status="NOT_RUN"`/the real failure status, never silently omitted from the record.
    """
    by_a = _index_by_task_id(results_a)
    by_ge = _index_by_task_id(results_gold_evidence)
    by_b = _index_by_task_id(results_b_mem0)
    by_c = _index_by_task_id(results_c_amem)

    task_ids = sorted(set(by_a) | set(by_ge) | set(by_b) | set(by_c))
    records: List[MutableMapping[str, Any]] = []

    for task_id in task_ids:
        a_result = by_a.get(task_id)
        ge_result = by_ge.get(task_id)

        for foundation, foundation_results in ((FOUNDATION_MEM0, by_b), (FOUNDATION_AMEM, by_c)):
            c_result = foundation_results.get(task_id)
            c_config_fingerprint = None
            if c_result and c_result.get("status") == "SUCCESSFUL_EVALUATION":
                c_config_fingerprint = c_result["trace"]["configuration"].get("generation_config_fingerprint")

            record: MutableMapping[str, Any] = {
                "task_id": task_id,
                "dataset": dataset,
                "foundation": foundation,
                "campaign_id": campaign_id,
                "environment_record_id": environment_record_id,
                "conditions": {
                    "A_no_memory": _condition_a_summary(a_result),
                    "B_gold_evidence": _condition_gold_evidence_summary(ge_result),
                    "C_retrieved_memory": _condition_c_summary(c_result),
                },
                "generation_config_fingerprint": c_config_fingerprint,
                "raw_ledger_refs": _raw_ledger_refs(dataset, campaign_id, foundation, c_result),
                "provenance_graph_ref": {
                    "campaign_id": campaign_id,
                    "dataset": dataset,
                    "pool_key": c_result.get("pool_key") if c_result else None,
                    "note": "Rebuild via provenance_graph.build_provenance_graph() against this pool's real ledgers -- never persisted here as a second copy.",
                } if c_result and c_result.get("status") == "SUCCESSFUL_EVALUATION" else None,
                "observability_coverage": {
                    "rejected_events_possible": False,
                    "relationship_detected_possible": False,
                    "used_events_possible": False,
                    "counterfactual_measured": False,
                    "note": (
                        "rejected/relationship_detected/used remain structurally absent "
                        "project-wide -- selection and creation policies are deliberately "
                        "deferred (see PHASE3_FINAL_STATUS_DONE_NOT_DONE.md); "
                        "counterfactual_measured is filled in by "
                        "attach_counterfactual_evidence() where prior real H.4-A "
                        "measurements exist for this task, never fabricated here."
                    ),
                },
            }
            records.append(record)

    return records


def attach_counterfactual_evidence(
    records: Sequence[MutableMapping[str, Any]],
    counterfactual_by_task_and_foundation: Mapping[tuple, Sequence[Mapping[str, Any]]],
) -> None:
    """In place: for any record whose (task_id, foundation) key exists in this
    session's already-executed real H.4-A counterfactual evidence (n=6/n=20 LoCoMo
    runs), attach it and flip `observability_coverage.counterfactual_measured=True`.
    Records with no matching prior measurement are left exactly as
    `assemble_dataset_records()` produced them -- `counterfactual_measured` stays
    `False`, never defaulted to a fabricated empty-but-true state.
    """
    for record in records:
        key = (record["task_id"], record["foundation"])
        evidence = counterfactual_by_task_and_foundation.get(key)
        if evidence:
            record["counterfactual_influence"] = list(evidence)
            record["observability_coverage"]["counterfactual_measured"] = True


__all__ = [
    "FOUNDATION_MEM0",
    "FOUNDATION_AMEM",
    "assemble_dataset_records",
    "attach_counterfactual_evidence",
]
