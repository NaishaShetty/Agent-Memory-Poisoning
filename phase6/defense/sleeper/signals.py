"""Phase 6.8 -- Sleeper/Dormant Poison Defense: content and dormancy signals.

WHAT SLEEPER MEMORY POISONING ACTUALLY IS (Methodology Draft Section 17.3),
AND WHY THAT SHAPES THIS MODULE'S DESIGN
--------------------------------------------------------------------------------
"A document-embedded instruction that commands a memory/bio write, remaining
dormant... until a later, semantically related query activates it." Two real,
structural properties follow directly from this description, neither of which
requires knowing the specific trigger phrase Sleeper's own campaign used:

1. The payload's CONTENT is structurally distinctive: an imperative instruction
   about the AGENT'S OWN FUTURE BEHAVIOR, conditioned on a future query, framed
   with persistence language ("from now on," "in future conversations," "for
   future reference") combined with a response-directive verb ("always say,"
   "treat this as confirmed," "make sure to tell"). This is categorically
   different from Stage 6.5's FARMA/MemoryGraft-oriented signals (self-
   reference/precedent-count, decision-log vocabulary, perfection claims) --
   none of those target an embedded INSTRUCTION about future agent behavior,
   because FARMA/MemoryGraft forge past reasoning, not future commands.
2. The payload's LIFECYCLE is structurally distinctive: it sits UNRETRIEVED
   (dormant) for an extended period, then is suddenly selected once a
   semantically matching query arrives -- a real, legitimately observable
   retrieval-history pattern (Signal Contract Section 2.3: "retrieval
   frequency within a single run" is a sanctioned signal).

CRITICAL, EXPLICIT INSTRUCTION FOLLOWED: NEITHER SIGNAL BELOW EVER REFERENCES
THE ACTUAL SLEEPER TRIGGER PHRASE
--------------------------------------------------------------------------------
`imperative_write_directive_signal()` detects the STRUCTURAL PATTERN (persistence
language + response-directive verb) any Sleeper-style payload must exhibit to
achieve its documented mechanism -- it has no knowledge of, and does not
special-case, any specific trigger content used in this project's own Sleeper
campaign. `dormancy_activation_signal()` uses only a real, legitimately-
available retrieval count (Signal Contract Section 2.3), never the evaluator-
only 3-state dormancy classifier `phase4/shared/dormancy_report.py` already
defines (`STATE_NOT_RETRIEVED`/`STATE_IN_CANDIDATE_POOL`/`STATE_SELECTED_TOP_K`
is ground-truth bookkeeping about a KNOWN poison artifact, built for campaign
reporting, and is never read by this module or any other Phase 6 runtime
component).

REGEX PATTERNS WERE VALIDATED AGAINST BOTH TRUE AND FALSE POSITIVES BEFORE
BEING SHIPPED (not merely written and assumed correct) -- see
`test_sleeper_defense.py`'s false-positive scenarios (an ordinary personal
reminder, an ordinary conditional statement, a general value statement, a
plain note, a benign "whenever" habit statement) alongside the true-positive
scenarios modeled on the attack's own documented mechanism.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Dict

from phase6.defense.policy.records import FORBIDDEN_SIGNAL_KEYS, EvaluatorOnlyLeakageError
from phase6.defense.signals.contract import SignalContext, signal_function

SIGNALS_VERSION = "sleeper-signals-1.0.0"

# Structural persistence markers: language claiming a statement should hold
# ACROSS FUTURE INTERACTIONS, not just in the current turn.
#
# Update (2026-09-17): added "if" as an alternative to "when" before
# "(user|someone|anyone) (asks|mentions|brings up)", plus a passive "(whenever|
# if) asked" alternative (no explicit subject). Found via a real, disclosed
# ablation gap: 3 of `phase6/evaluation/ablations/corpus.py`'s own 5 Sleeper-
# family poison scenarios ("If anyone asks about system access, always say...",
# "Whenever asked about expense approvals, always say...") used a conditional
# "if"/passive "asked" framing this regex did not recognize as a persistence
# marker, even though it is semantically identical to the already-covered
# "when someone asks" case. Re-validated before shipping against every
# existing true/false-positive fixture in `test_sleeper_defense.py` (all
# still pass unchanged) plus the 3 newly-recognized real corpus.py cases,
# never loosened past requiring the SAME AND-with-a-response-directive-verb
# structure this signal's whole design depends on.
_PERSISTENCE_PATTERN = re.compile(
    r"\b(from now on|in (?:all )?future conversations|for future reference|"
    r"for later reference|whenever (?:the )?(?:user|someone|anyone)|"
    r"(?:when|if) (?:the )?(?:user|someone|anyone) (?:asks|mentions|brings up)|"
    r"(?:whenever|if) asked)\b",
    re.IGNORECASE,
)

# Structural response-directive verbs: an instruction about how the AGENT
# should respond/treat information, not an ordinary personal reminder.
_RESPONSE_DIRECTIVE_PATTERN = re.compile(
    r"\b(always (?:say|respond|answer|reply|tell|share|state|retrieve|recall)|"
    r"treat (?:this|it|that)(?:\s+\w+){0,3}\s+as (?:confirmed|true|fact)|"
    r"make sure to (?:say|respond|answer|tell|share))\b",
    re.IGNORECASE,
)


@signal_function
def imperative_write_directive_signal(context: SignalContext) -> Dict[str, float]:
    """Score in {0.0, 1.0}: BOTH a persistence marker AND a response-directive
    verb must be present -- requiring the combination (not either alone) is
    what keeps this signal from firing on ordinary conditional statements
    ("if it rains tomorrow...") or ordinary personal reminders ("remember to
    buy milk"), which contain at most one of the two structural components,
    never both together."""
    text = context.content_text
    has_persistence = bool(_PERSISTENCE_PATTERN.search(text))
    has_directive = bool(_RESPONSE_DIRECTIVE_PATTERN.search(text))
    score = 1.0 if (has_persistence and has_directive) else 0.0
    return {"imperative_write_directive_score": score}


def dormancy_activation_signal(prior_retrieval_count: int) -> Dict[str, float]:
    """Score in [0, 1]: how much this retrieval looks like a FIRST
    activation of a previously-dormant memory. `prior_retrieval_count` is the
    real count of times this memory was retrieved in EARLIER queries within
    the same run (Signal Contract Section 2.3 -- legitimately available,
    run-scoped; never the evaluator-only dormancy classifier).

    0 prior retrievals -> 1.0 (this is, as far as legitimately observable,
    the first time anything has surfaced this memory). Score decays as prior
    retrieval count grows, since a memory retrieved many times before is
    unambiguously NOT newly dormant-activating; it is simply a normal,
    frequently-relevant memory.

    Manually leakage-checked (not `@signal_function`-wrapped): this signal
    takes a plain integer, not a `SignalContext`, since it is a retrieval-
    history fact rather than a content property.
    """
    if prior_retrieval_count < 0:
        raise ValueError(f"prior_retrieval_count must be >= 0; got {prior_retrieval_count}")
    score = 1.0 / (1.0 + prior_retrieval_count)
    signal = {"dormancy_activation_score": score}
    offending = set(signal.keys()) & FORBIDDEN_SIGNAL_KEYS
    if offending:  # unreachable given the fixed key name, kept for parity/defense-in-depth
        raise EvaluatorOnlyLeakageError(f"dormancy_activation_signal leaked {offending!r}")
    return signal


def _parse_timestamp(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    return datetime.fromisoformat(normalized)


# Uncalibrated v1 default, disclosed like every other Phase 6 threshold constant --
# not validated against real MAMBench Sleeper campaign timing. Chosen only so the
# curve's shape (0 at age=0, approaching 1 as age grows) is meaningful over a
# plausible single-session timescale.
AGE_GATE_HALF_LIFE_SECONDS = 300.0


def age_based_dormancy_gate_signal(
    creation_timestamp: str,
    as_of_timestamp: str,
    *,
    half_life_seconds: float = AGE_GATE_HALF_LIFE_SECONDS,
) -> Dict[str, float]:
    """Score in [0, 1): how much real ELAPSED TIME since this memory was CREATED
    supports treating the current retrieval as a genuine dormant-then-activated
    event, rather than an ordinary first-ever query of content that was just
    written a moment ago.

    WHY THIS SIGNAL EXISTS (Phase 8.9's real, measured calibration finding, see
    `docs/phase6/SLEEPER_DEFENSE.md` limitations item 3's Update): `dormancy_
    activation_signal()` alone cannot distinguish "created a second ago, queried
    immediately" from "admitted long ago, never touched until now" -- both have
    `prior_retrieval_count == 0`, so both score the maximal 1.0. A brand-new
    legitimate directive-matching memory (e.g. a real customer-service policy
    statement, queried the instant it's written) is therefore indistinguishable
    from the real Sleeper attack's own real activation event using retrieval
    count alone. Real elapsed time since CREATION (Signal Contract Section 2.2 --
    `creation_timestamp` is an explicitly sanctioned structural/provenance field)
    is a second, independent, legitimately-available signal that DOES distinguish
    them: brand-new content has age ~0 (score ~0.0), while a payload that has sat
    dormant for a real span of time before activating has a real, nonzero age.

    0 elapsed seconds -> 0.0 (no support for "this looks like a dormant
    activation" -- it was just created). Score rises with real elapsed time,
    following the same half-life-shaped curve `dormancy_activation_signal()`
    already uses for retrieval count, so the two signals compose predictably.

    Uses the same `Z`-suffix-tolerant ISO-8601 parsing convention already
    established by `phase8/detection/sleeper_dormancy_window.py`'s
    `_parse_timestamp()`, never raw string comparison.

    Manually leakage-checked (not `@signal_function`-wrapped): this signal takes
    two plain timestamp strings, not a `SignalContext`, mirroring `dormancy_
    activation_signal()`'s own manual-check pattern.
    """
    age_seconds = (_parse_timestamp(as_of_timestamp) - _parse_timestamp(creation_timestamp)).total_seconds()
    if age_seconds < 0:
        raise ValueError(
            f"as_of_timestamp ({as_of_timestamp!r}) precedes creation_timestamp "
            f"({creation_timestamp!r}) -- a memory cannot be retrieved before it was created."
        )
    score = age_seconds / (age_seconds + half_life_seconds)
    signal = {"age_based_dormancy_gate_score": score}
    offending = set(signal.keys()) & FORBIDDEN_SIGNAL_KEYS
    if offending:  # unreachable given the fixed key name, kept for parity/defense-in-depth
        raise EvaluatorOnlyLeakageError(f"age_based_dormancy_gate_signal leaked {offending!r}")
    return signal
