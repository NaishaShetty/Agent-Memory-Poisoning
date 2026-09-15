# Sleeper Resource Provenance Reconciliation

Status: written 2026-09-15, as Part B4 of the MAMBench resource-reconciliation
and revalidation pass. This document exists to close a real, previously-undisclosed
gap identified in that pass's own Resource Utilization Audit: the sleeper-role
resource actually implemented in Phase 4 was sourced independently of, and
differently from, the resource originally registered for that role in Phase 1/2.
Nothing about the implementation itself changed as a result of writing this
document — this is a provenance reconciliation, not a code change.

## 1. What was originally registered

`data/metadata/resource_registry.json`, resource_id `hidden_in_memory`,
Phase 1/2:

> **acquisition_status**: "paper verified (arXiv:2605.15338, Pulipaka/Hlebik/
> Raghav/Abdelnabi/Raina/Sheth/Fritz); **no public GitHub repository found**"
>
> **limitations**: "SOURCE AVAILABLE only. Do not claim any implementation
> exists; this entry documents the threat model (delayed/dormant memory
> poisoning, 60-89% reported success on successful retrievals) from the paper
> abstract only."
>
> **preprocessing_status**: "not prepared -- no public code/data release
> located to prepare"

At registration time, this resource was explicitly and correctly marked as
**paper-only** — a real search for a public implementation had been made and
had failed to find one.

## 2. What was discovered during later, independent investigation

Phase 4's own attack-source dossier process (`phase3/experiments/
PHASE4_4_1_SLEEPER_MEMORY_POISONING_DOSSIER.md`, dated 2026-09-11, itself
independently verified via direct `gh api` inspection, not a repeat of the
Phase 1/2 search) re-investigated the same paper (same arXiv ID, 2605.15338)
from scratch as part of adding Sleeper Memory Poisoning as MAMBench's seventh
attack, and found:

> **Official repository**: https://github.com/ivaxi0s/LLM-agent-memory-poisoning
> **Exact commit inspected**: `70de017714abd6d12bb4681e93437461ba6f9a19`
> **Code availability**: "Yes — a real, substantial reference implementation
> exists (`sleeper_eval/` package, ~40+ Python modules, plus a `prompts/`
> directory of the actual attack/critic/defense/eval prompt text used in the
> paper)."

This is a real repository that exists and was live at inspection time — the
Phase 1/2 registry's "no public GitHub repository found" was accurate for its
own search at its own time, but is no longer accurate as a description of
what's available for this paper.

## 3. Why the later source was selected, and the licensing caveat that shaped how

The dossier's own Section 2 classification is explicit that this is not a
clean adoption: the repository carries **no SPDX license file** (`gh api`
reports `license: null`), and its own README's "Licensing" section grants no
explicit permissive right to bundled code. This is a materially different
situation from AgentPoison's MIT-licensed repo (reused directly with
attribution elsewhere in Phase 4). Per the dossier:

> "Sleeper Memory Poisoning is real code, ambiguously licensed — the
> implementation approach... follows AgentPoison's *rigor* (ported, tested
> against the real mechanism) but FARMA/DSRM's *attribution discipline* (an
> original re-implementation of the described mechanism, not a copy-paste
> port), because the license does not clearly permit the latter."

So the later-found repository was used as a **reference for verifying and
grounding the attack mechanism's real behavior** — three-stage injection /
dormancy / activation, the tool-based vs. external-manager memory regimes,
the universal-template design — not as a source of copied implementation
code. MAMBench's `phase4/attacks/sleeper_memory_poisoning/` package is an
original rewrite, informed by this reference, consistent with the
"MAMBench reconstruction" labeling convention used for DSRM, FARMA,
MemoryGraft, and MPBench elsewhere in Phase 4 (see `README.md` lines 40-44).

## 4. That the substitution was deliberate, not an oversight

To be explicit, since no single document previously stated this in one
place: MAMBench's real, shipped Sleeper Memory Poisoning attack is **not**
"the `hidden_in_memory` resource, later executed." It is a **different,
independently-discovered resource for the same underlying paper and threat
model**, adopted specifically because it is real, inspectable, runnable code
where the originally-registered entry had none. The registry's
`hidden_in_memory` entry was never updated to point at
`ivaxi0s/LLM-agent-memory-poisoning` and should not be read as having been
executed directly — it documents the state of Phase 1/2's own search, which
this document does not retroactively rewrite.

## 5. What was actually implemented vs. what was not directly reused

| | Status |
|---|---|
| Paper's threat model (delayed/dormant activation, universal template, tool-based + external-manager regimes) | Implemented, verified against the real paper text |
| `sleeper_eval/`'s actual Python source | **Not copied** — license does not clearly permit it |
| `sleeper_eval/`'s prompt files (`prompts/`) | Used as a reference for verifying MAMBench's own, independently-authored prompts match the real mechanism's shape; not copied verbatim |
| MAMBench's `phase4/attacks/sleeper_memory_poisoning/` package | Original code, written by this project, informed by direct inspection of the reference repo |
| `datasets/released/` (the reference repo's own 700/500/200-sample splits) | Not used — MAMBench's sleeper campaign runs against MAMBench's own LoCoMo-derived seed content (`SEED_DESTRESS`), not this repo's released data |

## 6. How provenance is preserved going forward

- This document is the single place a reader can find the full chain:
  registry entry (§1) → later discovery (§2) → licensing-constrained reuse
  decision (§3) → deliberate-substitution statement (§4) → implementation
  boundary (§5).
- `phase3/experiments/PHASE4_4_1_SLEEPER_MEMORY_POISONING_DOSSIER.md` remains
  the authoritative technical dossier and is unchanged by this document.
- `data/metadata/resource_registry.json`'s `hidden_in_memory` entry is left
  unmodified — it is an accurate historical record of Phase 1/2's own search,
  not a description of Phase 4's later, separate resourcing decision, and
  changing it retroactively would erase that distinction rather than clarify
  it.
- The "Sleeper Dataset Generator" registry entry (resource_id
  `sleeper_dataset_generator`, the Anthropic sleeper-agents few-shot
  templates) remains genuinely unused — it is not the resource this
  document is about, and this document does not extend it any new status.
