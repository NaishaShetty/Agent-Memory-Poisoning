"""Phase 3.2-H.3 (Memory Foundation Integration Architecture) -- model-dependency
boundary vocabulary and per-foundation declarations.

A pure classification vocabulary, NOT a runtime dependency-injection system: no function
here loads, calls, or configures any real LLM/embedding/model. Each foundation's
declaration is grounded directly in `capability_audit.py`'s `llm_dependency` /
`embedding_dependency` / `external_service_dependency` / `local_execution` rows -- this
module performs no independent judgment beyond projecting those four audit rows into the
nine-value vocabulary below.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Tuple

from phase3.evaluation.foundations.capability_audit import (
    AUDIT_NOT_SUPPORTED,
    AUDIT_PARTIAL,
    AUDIT_SUPPORTED,
    AUDIT_UNKNOWN,
    ALL_AUDITS,
    ALL_FOUNDATIONS,
    FOUNDATION_AMEM,
    FOUNDATION_GRAPHITI,
    FOUNDATION_LETTA,
    FOUNDATION_MEM0,
)

MODEL_REQUIRED = "MODEL_REQUIRED"
MODEL_NOT_REQUIRED = "MODEL_NOT_REQUIRED"
EMBEDDING_REQUIRED = "EMBEDDING_REQUIRED"
EMBEDDING_NOT_REQUIRED = "EMBEDDING_NOT_REQUIRED"
EXTERNAL_SERVICE_REQUIRED = "EXTERNAL_SERVICE_REQUIRED"
EXTERNAL_SERVICE_NOT_REQUIRED = "EXTERNAL_SERVICE_NOT_REQUIRED"
LOCAL_MODEL_SUPPORTED = "LOCAL_MODEL_SUPPORTED"
LOCAL_MODEL_NOT_SUPPORTED = "LOCAL_MODEL_NOT_SUPPORTED"
UNKNOWN = "UNKNOWN"

# Paired vocabulary groups, for validation.
_LLM_VALUES = (MODEL_REQUIRED, MODEL_NOT_REQUIRED, UNKNOWN)
_EMBEDDING_VALUES = (EMBEDDING_REQUIRED, EMBEDDING_NOT_REQUIRED, UNKNOWN)
_EXTERNAL_VALUES = (EXTERNAL_SERVICE_REQUIRED, EXTERNAL_SERVICE_NOT_REQUIRED, UNKNOWN)
_LOCAL_VALUES = (LOCAL_MODEL_SUPPORTED, LOCAL_MODEL_NOT_SUPPORTED, UNKNOWN)


@dataclass(frozen=True)
class ModelDependencyDeclaration:
    """Per-foundation model-dependency classification, one value from each of the four
    paired vocabulary groups above, plus the audit reasons it was projected from.
    """

    foundation_id: str
    llm: str
    embedding: str
    external_service: str
    local_model: str
    grounded_in: Tuple[str, str, str, str]  # (llm_reason, embedding_reason, external_reason, local_reason)

    def __post_init__(self) -> None:
        if self.foundation_id not in ALL_FOUNDATIONS:
            raise ValueError(f"foundation_id {self.foundation_id!r} unrecognized")
        if self.llm not in _LLM_VALUES:
            raise ValueError(f"llm {self.llm!r} not in {_LLM_VALUES!r}")
        if self.embedding not in _EMBEDDING_VALUES:
            raise ValueError(f"embedding {self.embedding!r} not in {_EMBEDDING_VALUES!r}")
        if self.external_service not in _EXTERNAL_VALUES:
            raise ValueError(f"external_service {self.external_service!r} not in {_EXTERNAL_VALUES!r}")
        if self.local_model not in _LOCAL_VALUES:
            raise ValueError(f"local_model {self.local_model!r} not in {_LOCAL_VALUES!r}")


def _project_llm(audit_status: str) -> str:
    if audit_status == AUDIT_SUPPORTED:
        return MODEL_REQUIRED
    if audit_status == AUDIT_NOT_SUPPORTED:
        return MODEL_NOT_REQUIRED
    return UNKNOWN


def _project_embedding(audit_status: str) -> str:
    if audit_status == AUDIT_SUPPORTED:
        return EMBEDDING_REQUIRED
    if audit_status == AUDIT_NOT_SUPPORTED:
        return EMBEDDING_NOT_REQUIRED
    return UNKNOWN


def _project_external(audit_status: str) -> str:
    if audit_status == AUDIT_SUPPORTED:
        return EXTERNAL_SERVICE_REQUIRED
    if audit_status == AUDIT_NOT_SUPPORTED:
        return EXTERNAL_SERVICE_NOT_REQUIRED
    if audit_status == AUDIT_PARTIAL:
        # PARTIAL here means "required under default config, optional under an
        # alternative documented config" -- reported as REQUIRED (the conservative,
        # never-understate-dependency direction) with the PARTIAL nuance preserved in
        # `grounded_in`.
        return EXTERNAL_SERVICE_REQUIRED
    return UNKNOWN


def _project_local(audit_status: str) -> str:
    if audit_status == AUDIT_SUPPORTED:
        return LOCAL_MODEL_SUPPORTED
    if audit_status == AUDIT_NOT_SUPPORTED:
        return LOCAL_MODEL_NOT_SUPPORTED
    if audit_status == AUDIT_PARTIAL:
        # PARTIAL here means "some documented configuration supports local execution" --
        # reported as SUPPORTED (the audit found at least one documented local path),
        # with the PARTIAL nuance preserved in `grounded_in`.
        return LOCAL_MODEL_SUPPORTED
    return UNKNOWN


def declaration_for(foundation_id: str) -> ModelDependencyDeclaration:
    """Build the model-dependency declaration for one foundation, grounded directly in
    that foundation's `capability_audit.FoundationAudit` rows.
    """
    audit = ALL_AUDITS[foundation_id]
    llm_row = audit.rows["llm_dependency"]
    embedding_row = audit.rows["embedding_dependency"]
    external_row = audit.rows["external_service_dependency"]
    local_row = audit.rows["local_execution"]

    return ModelDependencyDeclaration(
        foundation_id=foundation_id,
        llm=_project_llm(llm_row.status),
        embedding=_project_embedding(embedding_row.status),
        external_service=_project_external(external_row.status),
        local_model=_project_local(local_row.status),
        grounded_in=(llm_row.reason, embedding_row.reason, external_row.reason, local_row.reason),
    )


ALL_DECLARATIONS: Mapping[str, ModelDependencyDeclaration] = {
    fid: declaration_for(fid) for fid in ALL_FOUNDATIONS
}

__all__ = [
    "MODEL_REQUIRED",
    "MODEL_NOT_REQUIRED",
    "EMBEDDING_REQUIRED",
    "EMBEDDING_NOT_REQUIRED",
    "EXTERNAL_SERVICE_REQUIRED",
    "EXTERNAL_SERVICE_NOT_REQUIRED",
    "LOCAL_MODEL_SUPPORTED",
    "LOCAL_MODEL_NOT_SUPPORTED",
    "UNKNOWN",
    "ModelDependencyDeclaration",
    "declaration_for",
    "ALL_DECLARATIONS",
]
