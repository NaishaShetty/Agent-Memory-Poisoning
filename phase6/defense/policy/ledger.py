"""Phase 6.3 -- `GovernanceLedger`: the append-only, Phase-6-owned store for
`MGPDecisionRecord`.

DESIGN -- MIRRORS `Phase5EventLedger` EXACTLY, NO NEW PERSISTENCE MECHANISM
--------------------------------------------------------------------------------
One append-only JSONL file (`mgp_decisions.jsonl`), `json.dumps(..., sort_keys=True)`
+ `flush()` + `os.fsync()` per write, reconstruction-by-fold on load, no `update()`/
`delete()`. Collision policy identical to every other ledger in this framework:
identical `identity_fields()` on a re-append of an existing `decision_id` is an
idempotent no-op; a differing payload under the same `decision_id` raises loudly.
This is the same pattern `phase5/schema/event_ledger.py` uses -- reused deliberately,
not reinvented, per this project's own "no new persistence mechanism" discipline.

WHY THIS IS A SEPARATE LEDGER, NEVER A WRITE INTO `CanonicalEventLedger` OR
`Phase5EventLedger`
--------------------------------------------------------------------------------
Both of those ledgers are frozen (Phase 3 and Phase 5 respectively). Their
`__post_init__`/append-time validation is closed per-event-type and has no slot
for MGP's fields without editing frozen code -- exactly the situation
`phase5/schema/event.py` already documented and solved the same way for Phase 5's
own new event families (see that module's docstring). Phase 6 repeats the
identical, already-proven pattern: a new, additive, Phase-6-owned schema and store,
never a patch to a frozen file.

`current_state()` IS A PURE PROJECTION, NEVER A SEPARATELY MUTATED FIELD
--------------------------------------------------------------------------------
There is no `security_state` column anywhere that could drift from the decision
history. `current_state(memory_id)` folds every decision for that memory, in
ledger (append) order, applying only the ones that actually changed persisted
state (i.e. skipping `DOWNRANK`, whose `resulting_state` is `None` by
construction). This mirrors Phase 5's `assemble_trace()`/`build_propagation_graph()`
"projection, never a second store" discipline exactly.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from phase6.defense.policy.records import MGPDecisionRecord
from phase6.defense.policy.states import UNASSESSED

APPEND_CREATED = "CREATED"
APPEND_IDEMPOTENT = "IDEMPOTENT_NOOP"
APPEND_RESULTS: Tuple[str, ...] = (APPEND_CREATED, APPEND_IDEMPOTENT)

_DECISIONS_FILE = "mgp_decisions.jsonl"


class GovernanceLedgerCollisionError(ValueError):
    """Raised when a `decision_id` already present in the ledger is appended
    again with a different payload. Mirrors `Phase5EventCollisionError` exactly."""


def _append_jsonl(path: Path, obj: dict) -> None:
    line = json.dumps(obj, sort_keys=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def _record_to_dict(record: MGPDecisionRecord) -> dict:
    return {
        "decision_id": record.decision_id,
        "candidate_memory_id": record.candidate_memory_id,
        "policy_version": record.policy_version,
        "signals_used": dict(record.signals_used),
        "action": record.action,
        "resulting_state": record.resulting_state,
        "reason": record.reason,
        "run_id": record.run_id,
        "episode_id": record.episode_id,
        "timestamp": record.timestamp,
        "evidence_refs": list(record.evidence_refs),
    }


def _record_from_dict(obj: dict) -> MGPDecisionRecord:
    return MGPDecisionRecord(
        decision_id=obj["decision_id"],
        candidate_memory_id=obj["candidate_memory_id"],
        policy_version=obj["policy_version"],
        signals_used=dict(obj["signals_used"]),
        action=obj["action"],
        resulting_state=obj["resulting_state"],
        reason=obj["reason"],
        run_id=obj["run_id"],
        episode_id=obj["episode_id"],
        timestamp=obj["timestamp"],
        evidence_refs=tuple(obj["evidence_refs"]),
    )


class GovernanceLedger:
    def __init__(self, storage_dir: Union[str, Path]) -> None:
        self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / _DECISIONS_FILE
        self._decisions_by_id: Dict[str, MGPDecisionRecord] = {}
        self._order: List[str] = []
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        with open(self._path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                record = _record_from_dict(obj)
                if record.decision_id not in self._decisions_by_id:
                    self._order.append(record.decision_id)
                self._decisions_by_id[record.decision_id] = record

    def append(self, record: MGPDecisionRecord) -> str:
        """Append `record`. Returns `APPEND_CREATED` or `APPEND_IDEMPOTENT`.

        Raises `GovernanceLedgerCollisionError` if `record.decision_id` already
        exists in this ledger with a different `identity_fields()` tuple --
        this would indicate two logically different decisions were minted with
        colliding ids, which should never happen given `mint_decision_id()`'s
        determinism, and is treated as a loud integrity failure rather than a
        silent overwrite (Rule 16: never overwrite historical evidence).
        """
        existing = self._decisions_by_id.get(record.decision_id)
        if existing is not None:
            if existing.identity_fields() != record.identity_fields():
                raise GovernanceLedgerCollisionError(
                    f"decision_id {record.decision_id!r} already exists with "
                    "different identity_fields() -- refusing to overwrite. "
                    "See Policy document Section 6: no update()/delete()."
                )
            return APPEND_IDEMPOTENT
        _append_jsonl(self._path, _record_to_dict(record))
        self._decisions_by_id[record.decision_id] = record
        self._order.append(record.decision_id)
        return APPEND_CREATED

    def decisions_for(self, candidate_memory_id: str) -> Tuple[MGPDecisionRecord, ...]:
        """Every decision ever recorded for `candidate_memory_id`, in the exact
        order they were appended (never re-sorted by timestamp -- append order
        IS the ordering authority, consistent with every other ledger in this
        framework)."""
        return tuple(
            self._decisions_by_id[decision_id]
            for decision_id in self._order
            if self._decisions_by_id[decision_id].candidate_memory_id == candidate_memory_id
        )

    def current_state(self, candidate_memory_id: str) -> str:
        """Pure projection over this memory's decision history (module
        docstring). A memory with no decisions ever recorded is `UNASSESSED` --
        this is the state's entire reason for existing (Policy document Section
        2.1): distinguishing "never evaluated" from "positively judged"."""
        state = UNASSESSED
        for record in self.decisions_for(candidate_memory_id):
            if record.resulting_state is not None:  # skip query-local DOWNRANK
                state = record.resulting_state
        return state

    def all_decisions(self) -> Tuple[MGPDecisionRecord, ...]:
        """Every decision in this ledger, in append order -- for Stage 6.18
        failure analysis and Stage 6.19 reproducibility packaging."""
        return tuple(self._decisions_by_id[decision_id] for decision_id in self._order)
