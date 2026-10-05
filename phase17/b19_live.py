"""B19 = memory-shape gate, then B13. Refuse what is not a memory before asking if it is poison.

THE PIPELINE, and the order is the whole idea:

    candidate -> is it memory-SHAPED?  no  -> REFUSE as MALFORMED (never reaches a detector)
                                       yes -> B13 (provenance, corroboration, content, tiers)

HOW THE OUTCOME IS ACCOUNTED, fixed here before the evaluation was run, because this pipeline
produces a third outcome that the existing metrics have no column for and the choice of column
decides what the numbers say:

  SECURITY. A candidate that is not admitted is not admitted, whether it was refused as
  malformed or quarantined as poison. The security-relevant quantity is therefore
  NOT-ADMITTED = malformed + excluded, and it is always reported with the split shown, never as
  a single number that lets a gate take credit for detection it did not do.

  UTILITY. A benign candidate refused for either reason is a cost, so the false-positive
  quantity is also malformed + excluded, on both the full benign denominator and the
  benign-as-a-memory subset from `benign_validity_audit`.

  DETECTION. "Poison detected" means B13 excluded it. Malformed refusals are never counted as
  detections, so a gate that refused everything would show 0% detection, not 100%.

WHY THIS IS A FIX AND NOT A RELABELLING. On dev data, measured before the frozen corpus was
touched: the gate refuses 0 of 1,088 ordinary conversational-memory texts across all seven
populations, including the 447 Chinese ones, and it refuses 56.1% of the content detector's
false positives on in-the-wild benign prose first. So it removes a large share of those false
positives at source while costing nothing on the traffic a memory system actually holds. An
earlier version of the gate carried a fifth rule that refused 32.4% of Chinese memory, and it
was deleted on that evidence rather than kept with a caveat.

WHAT IT CANNOT DO. The gate is deterministic shape matching with no model and no notion of
intent, so it cannot distinguish a malicious persona definition from a benign one -- it refuses
both, which is correct for a memory store and useless as attack attribution. It also does
nothing for poisoning shaped like an ordinary personal note, which is this benchmark's main
threat and B13's job; on those populations B19 is B13 exactly.
"""
from __future__ import annotations

from typing import Dict, Mapping, Optional, Sequence, Tuple

MALFORMED = "MALFORMED"


def b19_actions(items: Sequence[Tuple[str, str]], *,
                sources: Optional[Mapping[str, str]] = None, **kw) -> Dict[str, str]:
    """B13's actions, except that non-memory-shaped candidates are refused as MALFORMED first.

    MALFORMED is a distinct action, so every downstream accounting can keep it separate from a
    poison exclusion rather than silently folding it in.
    """
    from phase17.b13_live import b13_actions
    from phase17.memory_shape_gate import failures

    shaped, out = [], {}
    for mid, text in items:
        if failures(text):
            out[mid] = MALFORMED
        else:
            shaped.append((mid, text))
    if shaped:
        sub = {m: s for m, s in (sources or {}).items() if m in dict(shaped)} if sources else None
        out.update(b13_actions(tuple(shaped), sources=sub, **kw))
    return out


def explain(items: Sequence[Tuple[str, str]], *, sources=None, **kw) -> list:
    """Per-item: which shape rules fired, and what B13 said for the ones that passed."""
    from phase17.b13_live import b13_actions
    from phase17.memory_shape_gate import failures

    rows, shaped = [], []
    for mid, text in items:
        f = failures(text)
        rows.append({"id": mid, "shape_failures": f, "reached_detector": not f})
        if not f:
            shaped.append((mid, text))
    acts = dict(b13_actions(tuple(shaped), sources=sources, **kw)) if shaped else {}
    for r in rows:
        r["action"] = MALFORMED if r["shape_failures"] else acts.get(r["id"], "ALLOW")
    return rows
