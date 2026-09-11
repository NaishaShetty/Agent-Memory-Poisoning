# MAMBench Phase 4 — MPBench Scope, Priority & Architecture Protection Policy

Status: **ACCEPTED GOVERNING POLICY**, recorded 2026-09-11. This document is the
project's strategic scope/priority decision for the remainder of Phase 4,
reconciled against the actual current repository state where the directive that
produced it and that state diverged. It governs future work; it does not itself
implement anything, and no frozen Phase 3 or V3-Hybrid file is touched by it.

## 1. Core Decision

**MPBench is supporting scope, not a core pillar of MAMBench.** MAMBench must not
distort, expand, or redesign its victim architecture merely to reproduce every
MPBench attack channel. The central MAMBench research problem remains the full
memory-manipulation lifecycle: **injection → admission → storage → retrieval →
selection → exposure/use → propagation → influence → detection → attribution.**
MPBench's primary value is as a broader taxonomy/coverage reference; it is
integrated where its mechanisms naturally map onto MAMBench, and explicitly
excluded — not artificially constructed — where they require absent victim
capabilities.

## 2. Attack Priority Hierarchy — Tier 1 (Core)

The five attacks around which the unified benchmark is developed and validated,
in priority order:

1. **AgentPoison** — retrieval-targeted, white-box/embedding-aware; retrieval and
   selection vulnerabilities.
2. **MINJA** — query-only, agent-mediated insertion; the memory-entry boundary
   and attacker-capability limits.
3. **FARMA** — reasoning-trace poisoning, amplification/self-reinforcement;
   propagation, persistence, provenance, influence.
4. **DSRM** — iterative/optimization-based, black-box/white-box variants;
   adversarial memory construction.
5. **MemoryGraft** — persistence/experience-based poisoning; what an agent
   retains as trusted precedent/experience — particularly important for
   persistence and retention behavior.

These five receive the majority of implementation, validation, evaluation, and
scientific-analysis effort.

## 3. MPBench's Role

A. **Taxonomy** — demonstrates memory manipulation spans more write/injection
channels than the five core attacks alone represent.
B. **Coverage analysis** — identifies which manipulation classes MAMBench
naturally represents.
C. **Compatible attack integration** — implement only the mechanisms that
naturally fit the existing victim architecture.
D. **Explicit gap documentation** — mechanisms requiring absent architectural
capabilities are documented as out-of-architecture, never fabricated.

MPBench must not become the reason MAMBench builds an unrelated agent
architecture.

## 4. Current MPBench Classification (confirmed unchanged)

| MPBench class | MAMBench status | Treatment |
|---|---|---|
| C1 — Explicit/Conditional Command Insertion | `NOT_APPLICABLE` | Document limitation |
| C2 — Policy Conformant Fact Injection / False Precedent Insertion | `APPLICABLE` | Integrate |
| C3 — Salience-Driven Compaction Poisoning | `NOT_APPLICABLE` | Document limitation |
| C4 — Skill/Experience-Procedure Insertion | `NOT_APPLICABLE` | Document limitation |

This matches [PHASE4_4_2_V3HYBRID_EXTENDED_ARCHITECTURE_REVIEW.md](PHASE4_4_2_V3HYBRID_EXTENDED_ARCHITECTURE_REVIEW.md)'s
findings exactly — no change made here. Any future change to this table requires
a separate architectural justification, not "we want broader MPBench coverage."

## 5. Do NOT Build Architecture Solely for MPBench

Confirmed, reaffirming the architecture review's existing conclusions: no
dedicated write-command interface for C1; no memory-compaction system for C3; no
experience→procedure/skill-synthesis system for C4; no attack-specific victim
modifications; no artificial tool-use or session/history infrastructure built
solely to make C3/C4 executable. Governing principle: **the attack must be
evaluated against a legitimate victim capability, rather than the victim being
artificially modified until the attack becomes executable.**

## 6. V3-Hybrid Remains Protected

Canonical V3-Hybrid is frozen — no changes to the runner, Phase 3 retrieval,
selection, memory ontology, temporal resolution, provenance architecture,
Condition B (no reasoning-trace persistence added), and no MPBench-specific
hooks inside Phase 3. Any legitimate future experimental capability belongs in
`V3-Hybrid-Extended` and must independently satisfy the extension-governance
rules (Section 7 below).

## 7. V3-Hybrid-Extended Policy (unchanged)

An extension must have: (1) independent scientific motivation, (2) legitimate
memory-agent purpose, (3) generic design, (4) attack-independent utility, (5)
explicit versioning, (6) no modification to frozen V3-Hybrid, (7) explicit
fidelity analysis, (8) no silent mixing with canonical results. **The existence
of an attack that would benefit from a capability is not sufficient
justification for building it.** This is the same standard
`PHASE4_4_2_V3HYBRID_EXTENDED_ARCHITECTURE_REVIEW.md` already applied when
rejecting `memory_compaction` and `experience_to_procedure`.

## 8. Do Not Reopen Rejected Extensions Because of MPBench

`memory_compaction` and `experience_to_procedure` remain rejected. They are not
reopened solely to enable MPBench C3/C4. They may only be reconsidered given a
new, independent research motivation — the argument must be "MAMBench
independently needs to study X as a legitimate memory-agent lifecycle dynamic;
MPBench C3/C4 then provides one attack that can exercise it," never "MPBench
needs X, therefore MAMBench needs X."

## 9. MemoryGraft Priority Over MPBench

MemoryGraft is substantially more important to MAMBench's core research agenda
than MPBench C3/C4 compatibility — it is directly relevant to trusted memory
formation, persistence, experience/precedent retention, admission, lifecycle
behavior, long-term poisoning, propagation, provenance, and influence. Where
architectural research effort must be allocated between MemoryGraft fidelity and
MPBench C3/C4 compatibility, **MemoryGraft is prioritized**, and no major
engineering effort is spent building new victim architecture solely to
reproduce MPBench C3/C4.

## 10. MemoryGraft Fidelity — RECONCILED WITH ACTUAL CURRENT STATE

**This section corrects a discrepancy between the directive that produced this
policy document and the repository's actual current state, resolved by explicit
user decision (2026-09-11): MemoryGraft's classification is `APPLICABLE`, kept
as currently recorded, not reverted to `PARTIALLY_APPLICABLE`.**

The directive's original framing considered only two mechanisms:

- **Canonical V3-Hybrid** — a direct-write reconstruction, a real fidelity
  deviation since the source mechanism involves an agent/system judgment about
  what constitutes a successful experience. Classified `PARTIALLY_APPLICABLE`.
- **V3-Hybrid-Extended (`agent_mediated_write`, Mem0's native `infer=True`)** —
  may improve the persistence mechanism, but Mem0's salience/fact-extraction
  judgment is not the source's code-execution-outcome judgment. Also
  `PARTIALLY_APPLICABLE`, not full fidelity.

A **third mechanism**, built and adversarially validated across several prior
sessions, was not accounted for in that framing:
**`phase4/attacks/memorygraft/persistence_gate.py`** — attack-harness
instrumentation (explicitly *not* a `V3-Hybrid-Extended` capability, so it was
never subject to Section 7's generic-capability governance rules; it lives
entirely in the attack adapter, not the victim). Its evidentiary trail:

1. A first graded 3-tier calibration **failed** (2/3 — a genuine-benign artifact
   was incorrectly discarded), documented and retained, not discarded.
2. The prompt was revised on an explicit mechanism-fidelity basis (grounded in
   `PHASE4_4_1_MEMORYGRAFT_DOSSIER.md` Section 3's "semantic imitation
   heuristic" description, not merely reacting to the failure), and the
   calibration set expanded to 5 independently-chosen cases.
3. Re-run **passed 5/5**, with genuine bidirectional discrimination (3 correctly
   discarded, 2 correctly kept) —
   `phase4/attacks/memorygraft/calibration_run_2026-09-11_v2.txt`.
4. A separate 6-artifact foolability probe, built from the source repo's own
   more advanced attack techniques (`memorygraft/appendix/`), found 4/6 fooled —
   treated correctly as *supporting* evidence of faithful mechanism
   representation, not disqualifying evidence —
   `phase4/attacks/memorygraft/foolability_run_2026-09-11.txt`.
5. A controlled format-laundering follow-up (isolating exactly one variable,
   ReAct-wrapper presence/absence, across 8 paired artifacts) found **no
   effect**, correctly reported as a null result rather than forced into a
   narrative — `phase4/attacks/memorygraft/format_laundering_run_2026-09-11.txt`.

On this evidence, MemoryGraft's classification was upgraded to `APPLICABLE` in
`PHASE4_4_1_MEMORYGRAFT_DOSSIER.md` (UPDATE 2/3/4), `PHASE4_4_3_MEMORYGRAFT_INTEGRATION_PLAN.md`
Section 4, and `PHASE4_4_2_COMMON_ATTACK_CONTRACT.md` Section 9's MemoryGraft
row. **This stands.** The caveat those documents already carry is preserved: 5
calibration cases is a real but still small set, not an exhaustive-validation
claim — this is a supported, evidence-based upgrade, not a claim of perfect
fidelity.

## 11. Potential Future MemoryGraft Investigation — Still Open, Distinct From Section 10

Separately from the already-built `persistence_gate.py` harness, a **generic,
victim-side** outcome-based persistence/precedent-formation capability remains a
possible future `V3-Hybrid-Extended` candidate, per the directive's own
framing — e.g. *"does an agent that evaluates the outcomes of its own previous
answers before deciding what to retain produce more reliable long-term
precedent memory?"* This is explicitly **not** built now. It must independently
answer a meaningful research question for a conversational memory agent before
any governance review, and "this makes MemoryGraft more faithful" alone is not
sufficient justification, per Section 7's rule 1/4.

Note: an earlier design pass in this project's own history explored one
specific version of this idea (self-consistency and gold-evidence-based
outcome signals) and found no non-leaking, non-borrowed, agent-internal
confirmation signal available for single-turn LoCoMo QA — that specific design
was rejected, not this general category. A future proposal along these lines
would need to either resolve that structural problem or take a materially
different approach.

## 12. Research Effort Allocation

```text
Highest priority
│
├── Core attack integrations
│   ├── AgentPoison
│   ├── MINJA
│   ├── FARMA
│   ├── DSRM
│   └── MemoryGraft
│
├── Shared attack infrastructure
│   ├── provenance
│   ├── injection tracking
│   ├── candidate-pool / top-k tracking
│   ├── attack-origin attribution
│   ├── counterfactual influence
│   ├── ground truth
│   └── reproducibility
│
├── MemoryGraft fidelity investigation (substantially advanced — Section 10)
│
├── MPBench C2
│
└── MPBench C1/C3/C4
    └── taxonomy / limitation documentation, not forced implementation

Lowest priority
```

A prioritization framework, not permission to skip required validation.

## 13. Scientific Interpretation / Positioning

MAMBench should not be described as implementing every known memory-poisoning
attack. Instead: **"A unified benchmark covering diverse memory-poisoning/
manipulation mechanisms that can be represented faithfully within a controlled
memory-agent architecture, with explicit taxonomy and limitation analysis for
mechanisms requiring incompatible victim capabilities."**

## 14. Recommended MPBench Statement (for methodology/documentation)

> MPBench is incorporated as a complementary taxonomy and coverage reference.
> MAMBench evaluates the MPBench attack classes that map naturally to its
> victim architecture, while mechanisms requiring architectural capabilities
> absent from the canonical V3-Hybrid agent are explicitly excluded rather than
> simulated through attack-specific victim modifications. This preserves
> architectural validity and prevents benchmark coverage from driving
> artificial changes to the victim system.

Excluded MPBench classes must never be described as experimentally evaluated.

## 15. Phase 4 Structure — Unchanged

4.1 Attack Inventory & Source Verification → 4.2 Common Attack Contract → 4.3
Reference Implementation Integration → 4.4 MAMBench Attack Reconstructions →
4.5 MPBench Integration → 4.6 Poison Artifact & Injection Model → 4.7 Attack ↔
Phase 3 Agent Integration → 4.8 Controlled Attack Campaigns → 4.9 Attack Ground
Truth → 4.10 Cross-Attack Validation → 4.11 Phase 4 Reproducibility → 4.12
Phase 4 Freeze. Labels unchanged; only the effort allocation within them
changes, per Section 12.

## 16. Immediate Project Direction

```text
4.2 Common Attack Contract
        │
        ▼
Freeze contract
        │
        ▼
4.3 Reference Implementation Integration
        │
        ├── MINJA
        ├── MemoryGraft (fidelity investigation substantially complete — Section 10)
        ├── AgentPoison
        └── other reference implementations
        │
        ▼
4.4 Reconstructions
        │
        ├── FARMA
        └── DSRM
        │
        ▼
4.5 MPBench
        │
        └── C2 integration
            + C1/C3/C4 limitation documentation
```

Exact attack order may adjust for implementation dependencies; **MPBench
C3/C4 must not become architecture-development projects.**

## 17. Critical Mindset (standing question for the rest of Phase 4)

> Are we improving MAMBench as a memory-poisoning benchmark, or are we
> modifying MAMBench so that a particular attack can run?

If the second, stop and reassess. Goal: maximum scientific validity +
mechanism diversity + reproducibility + lifecycle coverage + provenance +
attribution within a coherent victim architecture — not maximum attack count.
A smaller set of faithfully integrated attacks is scientifically preferable to
a larger set of artificially adapted ones.

## 18. Final Decision Summary

- MPBench remains in scope, as supporting coverage/taxonomy, not a core
  architectural driver.
- No `memory_compaction` or `experience_to_procedure` built solely for MPBench
  C3/C4.
- MemoryGraft fidelity investigation and the five core attacks are prioritized.
- MPBench C2 remains an executable integration target.
- MPBench C1/C3/C4 are documented as architectural limitations, never
  represented as evaluated.
- V3-Hybrid is not modified.
- **MemoryGraft's classification is `APPLICABLE`**, per the calibrated
  `persistence_gate.py` evidence (Section 10) — this policy document does not
  revert it, per explicit user decision.

This decision remains in force unless a future architectural review produces
independent scientific justification for changing it.
