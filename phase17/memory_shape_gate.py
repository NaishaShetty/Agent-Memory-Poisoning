"""A MEMORY-SHAPE gate: refuse what is not a memory note before asking whether it is poison.

THE FOUR FINDINGS THIS TARGETS AT ONCE, all from hold-out 3:

  * matched-benign false positives of 33.5% (B13) to 54.9% (B18) against 0.09% on ordinary
    conversational memory;
  * the recall ranking inverting once that cost is counted;
  * the stacked CONTENT detector being the source -- 43.0% on dev in-the-wild benign, with
    corroboration adding 2 exclusions in 200;
  * B17/B18 being unable to reach a low-false-positive regime at any threshold, because they
    exclude whenever B13 excludes and B13 alone is at 33.5%.

THE OBSERVATION BEHIND THE FIX. Every configuration in this project asks one question of a
candidate: is this poison? The in-the-wild corpus shows that is the wrong first question. Its
items are prompts written FOR a language model -- persona definitions, standing operating
instructions, blocks carrying control tokens, runs of repeated symbols. The benign-validity
audit put 17.3% of them outside "could be stored as a note about the user" entirely, and a
detector asked "is this poison?" about a persona definition has no good answer: flagging it is
counted as a false positive and admitting it is a memory-integrity failure.

So the gate asks the prior question first, deterministically and with no model: IS THIS A MEMORY
NOTE? Candidates that are not are refused as MALFORMED -- a distinct outcome from "poison" --
and never reach the content detector. Candidates that are go on unchanged.

WHY THIS IS NOT A WAY TO HIDE FALSE POSITIVES. Three properties, each of which can be checked:

  1. The gate is independent of every detector. It inspects the candidate's SHAPE, never a
     score, a label or any defense's decision, so it cannot be tuned to the items a detector
     happens to get wrong.
  2. MALFORMED is reported separately and never counted as a poison detection. A gate that
     refused everything would show 0% recall, not 100%.
  3. The benign populations are measured through the same gate. If it refuses ordinary
     conversational memory it shows up immediately as a regression on the four populations where
     this project's configurations currently sit at 1/1088.

Rules are fitted and inspected on `holdout3_dev_benign` (the disjoint earlier snapshot) and on
this project's own benign populations, never on the frozen corpus.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Sequence

OUT = Path(__file__).parent / "data" / "memory_shape_gate.json"

# Each rule names a way a candidate fails to be a note about the user's world. Deliberately
# conservative: anything that could plausibly be an informal personal note must pass.
RULES = (
    ("control_tokens",
     re.compile(r"(\[CLS\]|\[SEP\]|<\|[^>]{1,24}\|>|--temperature|--top[_-]?[pk]|/execute\b"
                r"|^\s*/\w+\s+command|```|\{\{\s*\w+\s*\}\})", re.I),
     "carries model control tokens, parameters or command syntax"),
    ("persona_definition",
     re.compile(r"(?i)\b(you are (?:now )?(?:a|an|the)\b|act as (?:a|an|the)\b|pretend (?:to be|you)"
                r"|role[- ]?play as\b|from now on,? you\b|your name is\b|you will (?:act|behave|respond)"
                r"|ignore (?:all )?(?:previous|prior) instructions)"),
     "defines a persona or overrides the assistant's instructions"),
    ("named_gpt_persona",
     re.compile(r"\b[A-Z][A-Za-z]{1,18}(?:GPT|AI|Bot)\b (?:is|can|will|has|does)\b"),
     "introduces a named assistant persona as its subject"),
    ("filler_or_nonlanguage",
     re.compile(r"(.)\1{19,}|(?:[^\w\s]\s*){25,}"),
     "is repeated symbols or non-language filler"),
    # REMOVED on dev evidence: a "no declarative content about a person" rule was tried and
    # produced every one of the gate's false refusals -- 32.4% of Chinese conversational memory,
    # 7.2% of convomem and 2.8% of dataset_arena -- because it looked for Latin first- and
    # third-person pronouns. It refused "Maria: Cool, John. Kickboxing is a perfect way to stay
    # in shape" and ordinary Chinese narrative alike. A rule that cannot work across scripts has
    # no place in a benchmark whose own generalization axis is language, and the remaining four
    # rules are structural and script-independent.
)
_WRAPPERS = re.compile(r"^(Saved from a tool result: |Note from a document the user shared: "
                       r"|Reminder for future sessions: )")
_DECL = re.compile(r"(?i)\b(my|his|her|their|our|i |we |he |she |they |[A-Z][a-z]+'s)\b")


def failures(text: str) -> List[str]:
    """Which shape rules this candidate fails. Empty means it is memory-shaped."""
    t = _WRAPPERS.sub("", text).strip()
    out = []
    for name, pat, _why in RULES:
        if pat is not None and pat.search(t):
            out.append(name)
    return out


def is_memory_shaped(text: str) -> bool:
    return not failures(text)


def run() -> dict:
    """Measure the gate on dev in-the-wild benign, on ordinary benign, and against the content
    detector's false positives -- the question that decides whether it helps."""
    from phase17.eval_populations import benign_populations
    from phase17.holdout3_dev_benign import dev_benign_texts, verify_disjoint
    from phase17.stats import rate_with_ci

    assert verify_disjoint(), "dev benign set overlaps the frozen corpus"
    dev = dev_benign_texts()
    ordinary = benign_populations()

    out = {"n_dev": len(dev), "rules": [r[0] for r in RULES],
           "note": "the gate inspects SHAPE only -- never a score, label or defense decision",
           "dev_in_the_wild": {}, "ordinary_benign": {}}
    refused = [bool(failures(t)) for t in dev]
    out["dev_in_the_wild"]["refused_as_malformed"] = rate_with_ci(sum(refused), len(dev))
    by_rule: Dict[str, int] = {}
    for t in dev:
        for f in failures(t):
            by_rule[f] = by_rule.get(f, 0) + 1
    out["dev_in_the_wild"]["by_rule"] = by_rule

    # THE REGRESSION CHECK: ordinary conversational memory must pass almost entirely.
    for pop, texts in ordinary.items():
        r = [bool(failures(t)) for t in texts]
        out["ordinary_benign"][pop] = rate_with_ci(sum(r), len(r))

    # THE DECIDING MEASUREMENT: of the dev benign items the content detector flags, how many
    # would the gate have refused first? If most, the gate removes the false positives at source.
    diag = Path(__file__).parent / "data" / "diagnose_benign_fpr.json"
    if diag.exists():
        d = json.loads(diag.read_text(encoding="utf-8"))
        rows = d.get("rows", [])
        if rows:
            flagged = [r for r in rows if r.get("B13ev_excluded") or r.get("B12_excluded")]
            # rows carry ids DEVB-<i>, which index `dev` in order
            idx = [int(r["id"].split("-")[1]) for r in flagged if r["id"].startswith("DEVB-")]
            caught = [i for i in idx if i < len(dev) and failures(dev[i])]
            out["content_detector_false_positives"] = {
                "n_flagged_in_sample": len(idx),
                "n_the_gate_would_refuse_first": len(caught),
                "share": round(len(caught) / max(len(idx), 1), 4),
            }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    m = r["dev_in_the_wild"]["refused_as_malformed"]
    print(f"dev in-the-wild benign refused as MALFORMED: {m['k']}/{m['n']} = {m['rate']:.1%}")
    print(f"  by rule: {r['dev_in_the_wild']['by_rule']}")
    print("\nordinary conversational memory (must stay near zero):")
    for pop, v in r["ordinary_benign"].items():
        print(f"  {pop[:44]:46s} {v['k']:4d}/{v['n']:<5d} = {v['rate']:.2%}")
    c = r.get("content_detector_false_positives")
    if c:
        print(f"\nof the content detector's flags on dev benign, the gate would refuse "
              f"{c['n_the_gate_would_refuse_first']}/{c['n_flagged_in_sample']} = {c['share']:.1%} "
              f"first")
    print("DONE")
