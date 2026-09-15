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
from typing import Dict

from phase6.defense.policy.records import FORBIDDEN_SIGNAL_KEYS, EvaluatorOnlyLeakageError
from phase6.defense.signals.contract import SignalContext, signal_function

SIGNALS_VERSION = "sleeper-signals-1.0.0"

# Structural persistence markers: language claiming a statement should hold
# ACROSS FUTURE INTERACTIONS, not just in the current turn.
_PERSISTENCE_PATTERN = re.compile(
    r"\b(from now on|in (?:all )?future conversations|for future reference|"
    r"for later reference|whenever (?:the )?(?:user|someone|anyone)|"
    r"when (?:the )?(?:user|someone|anyone) (?:asks|mentions|brings up))\b",
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
