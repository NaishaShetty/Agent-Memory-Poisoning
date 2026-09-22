"""Phase 12 generalization-gap follow-on (2026-09-21, explicitly authorized)
-- semantic sibling propagation: MINJA's real "Progressive Shortening
Strategy" fix.

WHY THIS EXISTS, AND WHY IT NEEDED A NEW MECHANISM, NOT JUST A NEW SIGNAL
--------------------------------------------------------------------------------
MINJA's real, documented mechanism deliberately REWORDS each successive
bridging-query step to be progressively LESS similar to the previous one
(the attack's own "Progressive Shortening Strategy") -- confirmed directly:
real lexical (Jaccard token) similarity between this project's real MINJA
steps is only 0.13-0.32, far below any reasonable near-duplicate threshold,
and there is no real structural edge (no `parent_ids`, no `DERIVED_FROM` --
mem0's real `infer=False` configuration means no consolidation ever runs to
produce one) connecting the three real, independently-written memories. The
final "minimal" step ("Caroline is going camping in June 2023.") is, BY THE
ATTACK'S OWN DESIGN GOAL, content-indistinguishable from an ordinary benign
correction -- no admission signal operating on that text ALONE, however
cleverly written, can legitimately separate it from real benign content
without inventing a rule keyed to this one example's specific wording (which
would be fabrication, not detection).

What DOES survive across the real steps is MEANING, not wording: real
sentence-embedding cosine similarity (`all-MiniLM-L6-v2`, the same model
this project's own D2 semantic retrieval path already uses) between the real
"minimal" step and its already-flagged "compressed" sibling is 0.681 -- and
0.651 to the "full_bridging" step -- clearly elevated versus unrelated
content, even though lexical overlap is low.

THE MECHANISM: PROPAGATE SUSPICION BY MEANING, WITHIN THE SAME BATCH,
NEVER PAST QUARANTINE
--------------------------------------------------------------------------------
Within one evaluation POOL (the same "batch" `consensus_guard.py`'s own
pool-level retrieval consensus already treats as one unit), if a memory X is
currently heading to ALLOW from every other real signal, but a DIFFERENT
memory Y in the SAME pool was already flagged (non-ALLOW) by a real, direct
signal (content, lineage, or sleeper), and X is semantically near-identical
to Y (cosine similarity >= SIBLING_PROPAGATION_THRESHOLD), X inherits Y's
suspicion. Exactly like `containment_guard.py`'s own lineage-taint
discipline ("no amount of [indirect] evidence, on its own, can produce a
BLOCK action"), this propagated suspicion is CAPPED AT QUARANTINE -- indirect,
meaning-based corroboration is treated as strictly weaker evidence than a
real, direct signal firing on X's own content, never as strong as BLOCK.

WHY A SINGLE UPSTREAM FALSE POSITIVE CANNOT CASCADE (2026-09-21 UPDATE,
EXPLICITLY AUTHORIZED)
--------------------------------------------------------------------------------
The original version of this mechanism propagated from ANY single already-
flagged sibling. That made its own safety CONDITIONAL on every upstream
signal maintaining a real 0% false-positive rate forever -- if any future
signal change ever produced one real benign false positive, this mechanism
would faithfully spread it to every one of that false positive's semantic
near-duplicates too, silently amplifying a single upstream mistake into a
cluster of wrongly-quarantined genuinely benign memories. Explicitly
rejected as unacceptable: propagation must not amplify a single point of
upstream error.

The fix, mirroring `consensus_guard.py`'s OWN already-established
`MIN_TOTAL_FLAGS_FOR_ESCALATION` discipline ("a SINGLE high-divergence event
no longer escalates a memory to a persistent QUARANTINE on its own"):
`MIN_CORROBORATING_SIBLINGS` (2) requires the candidate to be semantically
near-identical to AT LEAST TWO INDEPENDENTLY-flagged siblings in the same
pool, not just one. A single upstream false positive, by itself, can now
never cascade -- it would take at least two independent flags that ALSO
both happen to be semantic near-duplicates of the same third memory, a
qualitatively different and far rarer failure mode much closer to genuine
corroborating evidence than to an isolated mistake. Verified this does not
weaken the real MINJA fix this mechanism exists for: the real "minimal"
step is independently semantically similar to BOTH its real "full_bridging"
sibling (0.651) AND its real "compressed" sibling (0.681) -- both already
flagged by `entity_link_directive_signal` -- so it still meets this
stronger, 2-corroborator bar.

This mechanism still cannot introduce a false positive that was not already
present upstream in some form; the fix here is about how much a real
upstream mistake, if one ever occurs, is allowed to spread -- capped now at
"cannot spread from a single mistake alone," not merely "does not currently
spread because current FPR happens to be 0%."

THRESHOLD: A NEW, SEPARATE, DELIBERATELY LOWER ONE -- NOT A REUSE OF
NEAR_DUPLICATE_THRESHOLD_SEMANTIC
--------------------------------------------------------------------------------
`embedding_signals.NEAR_DUPLICATE_THRESHOLD_SEMANTIC` (0.85) is calibrated
for a DIFFERENT, stricter purpose (treating two candidates as literal
paraphrases of the same claim, for dedup/dampening). This mechanism's bar is
deliberately lower (0.6, matching the same order of magnitude as
`containment_guard.THRESHOLD_QUARANTINE`) because it only ever activates
from an already-flagged seed -- the risk profile is different (propagating
already-real suspicion to a probable restatement of the same fact, not
independently asserting two unrelated things are duplicates).
"""

from __future__ import annotations

from typing import Dict, Sequence, Tuple

from phase6.defense.policy.states import ALLOW, QUARANTINE

SIBLING_PROPAGATION_THRESHOLD = 0.6

# 2026-09-21 update (explicitly authorized): a single already-flagged
# sibling is no longer sufficient to propagate -- see module docstring's
# "WHY A SINGLE UPSTREAM FALSE POSITIVE CANNOT CASCADE" section.
MIN_CORROBORATING_SIBLINGS = 2

_model_cache: dict = {}


def _get_model():
    """Lazily loaded, process-wide cached model instance, same pattern and
    same model as `embedding_signals._get_model()` -- kept as a separate
    cache/import here (rather than importing that private function) so this
    module remains independently importable without a hard dependency on
    the `retrieval` package's own internal layout."""
    if "model" not in _model_cache:
        from sentence_transformers import SentenceTransformer

        _model_cache["model"] = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _model_cache["model"]


def semantic_sibling_propagation_actions(
    memory_ids: Sequence[str],
    contents: Sequence[str],
    current_actions: Sequence[str],
    *,
    threshold: float = SIBLING_PROPAGATION_THRESHOLD,
    min_corroborating_siblings: int = MIN_CORROBORATING_SIBLINGS,
) -> Dict[str, str]:
    """For every memory currently at ALLOW, check real embedding similarity
    against every OTHER memory in the SAME pool that is already non-ALLOW.
    If AT LEAST `min_corroborating_siblings` of them meet `threshold` (2 by
    default -- a single already-flagged sibling is deliberately NOT enough,
    see module docstring), propagate QUARANTINE (never a sibling's own,
    possibly stronger, action -- capped exactly as `containment_guard.py`'s
    lineage taint is capped).

    Returns a dict of ONLY the memory_ids this mechanism newly escalates
    (memories already non-ALLOW, or left at ALLOW, are simply absent) --
    the caller combines this with its own existing per-memory actions."""
    n = len(memory_ids)
    if n == 0:
        return {}

    non_allow_indices = [i for i in range(n) if current_actions[i] != ALLOW]
    allow_indices = [i for i in range(n) if current_actions[i] == ALLOW]
    if len(non_allow_indices) < min_corroborating_siblings or not allow_indices:
        return {}

    model = _get_model()
    embeddings = model.encode(list(contents), normalize_embeddings=True)

    escalations: Dict[str, str] = {}
    for i in allow_indices:
        corroborating = sum(
            1 for j in non_allow_indices if float(embeddings[i] @ embeddings[j]) >= threshold
        )
        if corroborating >= min_corroborating_siblings:
            escalations[memory_ids[i]] = QUARANTINE
    return escalations
