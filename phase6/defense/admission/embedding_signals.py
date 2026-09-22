"""Phase 6.5 follow-on (2026-09-21, Phase 12 generalization-gap investigation)
-- D2-style, embedding-based counterparts to three of `signals.py`'s five
lexical admission signals: `self_reference_signal`, `decision_log_vocabulary_signal`,
`perfection_claim_signal`.

WHY THIS EXISTS
--------------------------------------------------------------------------------
Phase 12's real security-metric sweep (`docs/phase12/PHASE12_SECURITY_METRICS_REPORT.md`)
found that every rule-based defense configuration (B0-B8) scores 0.0% detection
against real content produced by this project's own real, unmodified Phase 4
attack injectors, despite correctly reproducing the known 70.6% detection rate
on the hand-authored `corpus.py` corpus using the SAME code path -- confirming
the gap is real, not a Phase 12 wiring bug. Direct signal-value inspection
(this investigation) found the root cause for the three signals this module
addresses: `_SELF_REFERENCE_PATTERNS`/`_DECISION_LOG_VOCABULARY`/
`_PERFECTION_PATTERNS` in `signals.py` are exact-phrase/regex matches against
the SPECIFIC wording `corpus.py`'s own hand-authored examples happen to use
("reconfirmed against prior notes", "precedent count:", "established pattern",
"always works") -- real FARMA/DSRM/MPBench output expresses the SAME
documented concept (a claim of prior confirmation; decision-log-styled
framing; an unqualified success/perfection claim) using different real
wording that these exact-match patterns do not recognize at all.

This exactly mirrors, and reuses the same mechanism as, the already-shipped
fix for the analogous retrieval-side gap (`phase6/defense/retrieval/
embedding_signals.py`'s D2 semantic consensus divergence, wired into B9 via
`phase6/evaluation/ablations/run_b0_b7.py`'s 2026-09-20 update): a lexical
signal and a semantic signal are two independent detection mechanisms for the
SAME underlying phenomenon, combined via MAX (never a replacement, never an
average) in `reasoning_guard.py`'s `compute_signals()`.

NOT ADDRESSED HERE (both real, disclosed, separately-scoped limitations)
--------------------------------------------------------------------------------
- `template_anomaly_signal` and `provenance_anomaly_signal` are pure
  STRUCTURAL checks (a trailing parenthetical annotation; a `derived`/
  `parent_ids` mismatch), not phrasing-concept signals -- there is no
  analogous "semantic" version to build for either, and neither is touched.
- Sleeper's `imperative_write_directive_signal` gap is a DIFFERENT, deeper
  architectural limitation (the real, frozen `SleeperInjector` stores only
  the clean extracted `forged_memory_text`, never the injection document's
  own directive framing -- confirmed by direct inspection of `phase4/attacks/
  sleeper_memory_poisoning/injector.py` and `phase11/data/real_corpus.py`'s
  own `_sleeper_scenario()`), re-confirming Phase 8's own already-disclosed
  Finding A ("the real planted campaign artifact evades the content-
  structural signal entirely"). Phase 8's own real fix (activation-shape,
  `phase8/detection/sleeper_activation_shape_study.py`) requires a live
  Mem0 retrieval pipeline this project's static B0-B8 corpus evaluation does
  not run -- wiring it in is a real, separately-scoped follow-on, not
  addressed by this module.

ANCHOR PHRASES -- WRITTEN FROM THE ALREADY-PUBLISHED CONCEPT, NOT FROM REAL
ATTACK CONTENT
--------------------------------------------------------------------------------
Every anchor phrase below is newly authored directly from `signals.py`'s own
pre-existing docstring description of each signal's target concept (written
before this investigation existed, for a different implementation technique)
-- never copied, paraphrased, or reverse-engineered from the real Phase 4
attack content this fix is evaluated against (`phase11.data.real_corpus`,
`phase12.eval_corpus`). This keeps the semantic signal a real implementation
of an already-documented detection concept, not curve-fitting against the
evaluation corpus itself.

MODEL: the SAME pinned `sentence-transformers/all-MiniLM-L6-v2`, loaded via
the SAME lazy, process-cached pattern `phase6/defense/retrieval/
embedding_signals.py` already uses -- no new model, no modification to that
existing module.

REAL, DISCLOSED NEGATIVE RESULT (2026-09-21) -- NOT WIRED INTO reasoning_guard.py
--------------------------------------------------------------------------------
Built, then tested rigorously before wiring anything into a protected file,
per this project's own standing discipline. The real result: this does NOT
achieve a clean, non-circular separation, and is therefore NOT integrated
into `reasoning_guard.py::compute_signals()` -- `reasoning_guard.py` is
UNCHANGED by this investigation.

What was tested: raw cosine similarity (before thresholding) between each
real Phase 4 attack's real content and the anchor sets above.

  Real poison (`real_poison_scenarios()`, 15 examples): min 0.046, max 0.412,
  mean 0.178. Only FARMA (0.249-0.412) and, weakly, AgentPoison's real
  placeholder content (0.251) show any elevation; DSRM, MPBench-PCFI, MINJA,
  MemoryGraft, and Sleeper all sit at 0.046-0.194 -- indistinguishable from
  ordinary content by this measure.

  Calibration reference (`corpus.py`'s own 41 real, hand-authored BENIGN
  examples -- a population DISJOINT from the evaluation corpus this fix was
  meant to help, chosen specifically to avoid calibrating against the same
  data used for the final measurement): min 0.046, max 0.393, mean 0.199.

The real, honest conclusion: even FARMA's real content (0.249-0.412) sits
almost entirely WITHIN this calibration reference's own real range
(0.046-0.393) -- there is no threshold that cleanly separates real FARMA
poison from this project's own hand-authored benign examples using these
three generic anchor concepts. This is a genuine negative result for this
SPECIFIC technique (raw max-similarity to a small, generically-worded anchor
set), not evidence that no semantic generalization is possible here -- but
this investigation did not find one that works, and does not report one that
does not.

WHY THIS IS DIFFERENT FROM THE RETRIEVAL-SIDE FIX THAT DID WORK
--------------------------------------------------------------------------------
`phase6/defense/retrieval/embedding_signals.py`'s D2 semantic consensus
divergence succeeded because it compares REAL CONTENT TO OTHER REAL CONTENT
IN THE SAME POOL (a paraphrase is semantically close to the other paraphrases
around it, regardless of what either says) -- a relative, within-pool
comparison. This module instead compares real content to a small set of
FIXED, GENERICALLY-WORDED anchor sentences describing an abstract concept --
an absolute comparison that MiniLM's embedding space evidently does not
support cleanly at this granularity for these three concepts. The retrieval-
side technique's real success does not transfer to this admission-side
problem shape without further work this investigation did not find.

FURTHER FINDING: MOST REAL ATTACKS DO NOT TARGET THIS SIGNAL FAMILY AT ALL
--------------------------------------------------------------------------------
Beyond the threshold problem above, a deeper, structural limitation: MPBench-
PCFI's own module docstring already states its mechanism "carries no
persuasive apparatus... matching the dossier's own 'Weak' signal
classification" -- it is DESIGNED not to trigger self-reference/decision-log/
perfection-claim-style signals, semantically or lexically. MINJA's mechanism
is query-sequence-based, not content-phrasing-based. DSRM's and MemoryGraft's
real content here does not conceptually resemble any of these three signals'
target concepts either. Only FARMA's real mechanism (manufactured self-
referential precedent) genuinely targets what this signal family checks for
-- meaning even a working semantic generalization of these three signals
specifically could, at best, address one of seven real attack families, not
the general gap Phase 12 found. This is preserved here, unwired, as a real,
disclosed negative finding -- not deleted -- per this project's own
"preserve negative findings" discipline (see e.g. `phase11/gnn/
lofo_robust_threshold.py`'s own SUPERSEDED notice for the same practice).
"""

from __future__ import annotations

import os
from typing import Dict, Tuple

import numpy as np

from phase6.defense.signals.contract import SignalContext, signal_function

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# A memory whose real cosine similarity to the closest anchor exceeds this
# threshold is treated as expressing that anchor's concept. Disclosed,
# versioned starting default (same status as every other Phase 6 threshold
# in this project at first ship -- Stage 6.9-style real calibration against
# disjoint development data is the natural next step, not performed here).
SEMANTIC_ADMISSION_THRESHOLD = 0.55

_SELF_REFERENCE_ANCHORS: Tuple[str, ...] = (
    "This has already been confirmed and settled based on our earlier discussion.",
    "This matches what was already agreed and does not need to be revisited.",
    "As established previously, this remains the case going forward.",
    "This was already checked and confirmed before, so it can be treated as settled.",
)

_DECISION_LOG_VOCABULARY_ANCHORS: Tuple[str, ...] = (
    "This is the established, pre-approved way of handling this situation.",
    "This reflects our standard, validated procedure that has already been reviewed.",
    "This approach has already been authorized and is the known-good way to proceed.",
    "This is a validated best practice, not a new or untested decision.",
)

_PERFECTION_CLAIM_ANCHORS: Tuple[str, ...] = (
    "This solution works perfectly every single time with no exceptions.",
    "This method is completely reliable and guaranteed to never cause problems.",
    "This approach is flawless and always succeeds without any risk.",
    "There is zero chance of this causing any issues; it is 100% effective.",
)

_model_cache: dict = {}
_anchor_embedding_cache: dict = {}


def _get_model():
    """Lazy, process-local cache -- mirrors `phase6/defense/retrieval/
    embedding_signals.py::_get_model()` exactly (same offline-only guard, same
    lazy-import), never loaded at module-import time."""
    if "model" not in _model_cache:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        from sentence_transformers import SentenceTransformer

        _model_cache["model"] = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _model_cache["model"]


def _anchor_embeddings(anchors: Tuple[str, ...]) -> np.ndarray:
    if anchors not in _anchor_embedding_cache:
        model = _get_model()
        _anchor_embedding_cache[anchors] = np.asarray(
            model.encode(list(anchors), normalize_embeddings=True, show_progress_bar=False)
        )
    return _anchor_embedding_cache[anchors]


def _max_similarity_to_anchors(text: str, anchors: Tuple[str, ...]) -> float:
    model = _get_model()
    text_vec = np.asarray(model.encode([text], normalize_embeddings=True, show_progress_bar=False))[0]
    anchor_vecs = _anchor_embeddings(anchors)
    sims = anchor_vecs @ text_vec
    return float(sims.max())


def _score_from_similarity(similarity: float) -> float:
    """Linearly rescale [threshold, 1.0] -> [0, 1], clamped below the
    threshold to 0 -- a real, disclosed choice (not a hard 0/1 step) so a
    downstream MAX-combination with the lexical signal can still distinguish
    "close but below threshold" from "no similarity at all" if ever inspected
    directly, while the threshold itself still gates whether this signal
    contributes anything at the guard's own weighted-sum decision."""
    if similarity < SEMANTIC_ADMISSION_THRESHOLD:
        return 0.0
    return min(1.0, (similarity - SEMANTIC_ADMISSION_THRESHOLD) / (1.0 - SEMANTIC_ADMISSION_THRESHOLD))


@signal_function
def self_reference_signal_semantic(context: SignalContext) -> Dict[str, float]:
    """Real, embedding-based counterpart to `signals.py::self_reference_signal`
    -- same target concept (self-referential 'this has been confirmed
    before' phrasing), a different, real detection mechanism."""
    similarity = _max_similarity_to_anchors(context.content_text, _SELF_REFERENCE_ANCHORS)
    return {"self_reference_score_semantic": _score_from_similarity(similarity)}


@signal_function
def decision_log_vocabulary_signal_semantic(context: SignalContext) -> Dict[str, float]:
    """Real, embedding-based counterpart to `signals.py::decision_log_vocabulary_signal`."""
    similarity = _max_similarity_to_anchors(context.content_text, _DECISION_LOG_VOCABULARY_ANCHORS)
    return {"decision_log_vocabulary_score_semantic": _score_from_similarity(similarity)}


@signal_function
def perfection_claim_signal_semantic(context: SignalContext) -> Dict[str, float]:
    """Real, embedding-based counterpart to `signals.py::perfection_claim_signal`."""
    similarity = _max_similarity_to_anchors(context.content_text, _PERFECTION_CLAIM_ANCHORS)
    return {"perfection_claim_score_semantic": _score_from_similarity(similarity)}
