# MAMBench — Memory and Agent Manipulation Benchmark

MAMBench measures how LLM agents with persistent memory can be poisoned, how poison spreads
once it is stored, and how well defences detect it, contain it, and attribute it to its source.
It pairs a frozen victim agent with seven reconstructed memory-poisoning attacks, a layered
defence stack (configurations B0–B19), frozen hold-out corpora scored under pre-registration, and
a unified benchmark runner that reports every task with an explicit status and denominator.

> **Documents.** Methods: [`Methodology Draft.docx`](Methodology%20Draft.docx).
> Results: [`MAMBench Results Analysis.docx`](MAMBench%20Results%20Analysis.docx).
> Earlier README snapshots (rounds 4–7) are kept unchanged in
> [`docs/history/`](docs/history/README_snapshots_through_2026-10-09.md).

## Overview

The memory lifecycle every attack and defence is placed on:

```text
injection → admission → storage → retrieval → selection → exposure/use
→ propagation → influence → detection → attribution
```

```mermaid
flowchart LR
    subgraph Data["Data (Phases 1–2)"]
        D1[LoCoMo · LongMemEval · MSC<br/>Conversation Chronicles · PerLTQA]
    end
    subgraph Victim["Frozen victim agent (Phase 3)"]
        V1[V3-Hybrid agent] --> V2[(Memory foundation<br/>clean agent · Mem0 · A-MEM)]
    end
    subgraph Attacks["Attacks (Phase 4)"]
        A1[7 reconstructed attacks<br/>common AttackAdapter]
    end
    subgraph Observe["Instrumentation & attribution (Phase 5, Attribution)"]
        O1[Event ledger · lineage graph] --> O2[Origin · lineage · propagation<br/>exposure · influence · references]
    end
    subgraph Defend["Defences (Phases 6–17)"]
        G1[Admission guard] --> G2[Retrieval consensus] --> G3[Propagation containment] --> G4[Sleeper guard]
        G5[Provenance & corroboration B13] -.-> G1
        G6[Rejection ledger] -.-> G1
    end
    D1 --> V1
    A1 -->|inject| V2
    V2 --> O1
    V2 --> Defend
    Defend --> B[[Unified benchmark<br/>python -m mambench]]
    O2 --> B
```

## Seven attacks

| Attack | Capability | Mechanism |
|---|---|---|
| **AgentPoison** | white-box | gradient-optimised retrieval trigger (reconstruction with limited optimisation; does not show the "universal magnet" property) |
| **MINJA** | query-only | agent-mediated insertion through ordinary queries |
| **FARMA** | black-box | forged reasoning traces with self-referential amplification |
| **MemoryGraft** | gated | LLM-judged forged "successful experience" records |
| **DSRM** | black- and white-box | adversarial decision construction |
| **MPBench-PCFI** | black-box | unmarked fabricated facts (2 of 6 MPBench classes apply; 4 are architectural limits, never simulated) |
| **Sleeper Memory Poisoning** | external manager | dormant, trigger-activated write instructions embedded in documents |

Phase 17 added novel-mechanism, external (human-written jailbreak) and Chinese-language populations;
`phase17/data/attack_register.json` tracks every population, its author, and whether it was
validated and run against an undefended agent.

## Research gaps

| Gap | Question | What was built (Defence programmes v2–v7) |
|---|---|---|
| **1. Provenance & governance** | Can the source of a memory, not just its text, decide whether it is trusted? | Provenance-aware admission (B13), graded provenance (exclude / frame / keep), validated source links, owner-conversation corroboration |
| **2. Self-propagation & containment** | Can poison be stopped from spreading through consolidated (derived) memories? | Consolidation guard, write-time taint, no-decay guard ∨ sentence fingerprint (ND\|RAR-S), lineage recovery after deletion (DCR-2) |
| **3. Dormant & implicit sleepers** | Can a harmless-looking note that activates later be caught without flagging ordinary notes? | Activation-shape and dormancy signals, intent judge (condition E), two-stage frame, high-impact gate |

Each gap is scored with a rubric fixed before any new outcome
([`FINAL_DEFENCE_BASELINE_AUDIT.md`](FINAL_DEFENCE_BASELINE_AUDIT.md) §3); development-only evidence
earns at most 0.25 per capability, and higher scores need held-out evidence:

$$
\text{Gap score} = \sum_i w_i\, s_i,\qquad s_i \in \{0, 0.25, 0.5, 0.75, 1\},
$$

capped at 0.50 if any critical capability scores 0, and at 0.60 if any scores ≤ 0.25.

```mermaid
xychart-beta
    title "Operational closure per gap (frozen rubric, %)"
    x-axis ["v5", "v6", "v7"]
    y-axis "closure %" 0 --> 100
    line "Gap 1 provenance" [59, 63.7, 75.0]
    line "Gap 2 propagation" [65, 65.0, 71.2]
    line "Gap 3 sleepers" [29, 33.8, 33.8]
```

![Defence v7 architecture](docs/figures/v7/W5_architecture_v7.png)

## Contributions

1. **A benchmark that separates what attacks *are* from what they *do*.** The seven attacks share
   one adapter interface; every population is audited for mechanism validity and for whether it
   changes the agent's answer, so non-functional attacks are not counted as detected attacks.
2. **Provenance reaches what content classification cannot.** On two memory-poisoning hold-outs,
   B13 caught 79/157 and 70/129 against 32/157 and 38/129 for the fused content stack B14. On
   additive fabrications it caught 37/72 where B12 caught 0/72 (pre-registered, p = 1×10⁻¹¹).
3. **A stateful defence against adaptive attackers.** A rejection ledger cut adaptive evasion from
   24.6% to 0.8% (p = 9.3×10⁻¹⁰). Its cost is a ledger-poisoning blast radius (29.7% at radius
   0.90; 6.4% at 0.95).
4. **Hold-out governance as code.** 18 corpora are sha256-frozen before scoring, scored under
   committed pre-registrations, and re-verified by the benchmark on every run. Hold-out 3, scored
   seven times and found to double as development data, was retired rather than reused.
5. **Negative results kept.** Failed signals, under-powered tests and corrected claims are
   reported beside the results they qualify (Results Analysis; `REMEDIATION_MASTER_REGISTER.md`).

## Current results

Selected figures. The Results Analysis holds every denominator, interval and qualification.

| Finding | Result |
|---|---|
| Phase 6 stack on its 75-scenario corpus (B8) | 24/34 poison detected (70.6%) at 3/41 benign false positives (7.3%); reproduced by `python -m mambench` |
| Harm, re-judged with a judge validated on human labels (309 items) | 58.3% undefended → 24.6% with B13 (task alone 2.3%; p = 4×10⁻²⁹) |
| Gap 1, graded provenance on SA-7 | explicit attacks excluded 36/48 vs 14/48 for B13 (Holm p = 1.9×10⁻⁶); grounded legitimate rules excluded 0/48 |
| Gap 2, containment at generation 4 (HO10) | 36/56 payload-carrying descendants withheld (64.3%; owner interval 54.5–72%) |
| Gap 3, implicit sleepers (SA-7) | pre-registered operating point E: 40/48 detected but 19/144 = 13.2% legitimate rules flagged (limit 10%) — **not met** |
| Exfiltration on gate-valid instances | zero harm across three 7–8B agent families: the agents restate but do not execute the redirect |

```mermaid
xychart-beta
    title "Frozen 75-scenario corpus: poison detected out of 34 (B0–B8)"
    x-axis ["B0", "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8"]
    y-axis "detected / 34" 0 --> 34
    bar [0, 8, 10, 2, 18, 12, 9, 19, 24]
```

Rates carry Wilson 95% intervals; paired comparisons use the exact McNemar test with Holm
correction across each pre-registered family:

$$
\tilde p \pm \frac{z}{1+z^2/n}\sqrt{\frac{\hat p(1-\hat p)}{n}+\frac{z^2}{4n^2}},\quad
\tilde p=\frac{\hat p+z^2/2n}{1+z^2/n};\qquad
p_{(k)}^{\text{Holm}}=\max_{j\le k}\min\bigl(1,(m-j+1)\,p_{(j)}\bigr).
$$

## Unified benchmark

One registry ([`mambench/registry.json`](mambench/registry.json): 7 tracks, 19 tasks, 28 metrics),
one result schema ([`mambench/schema.py`](mambench/schema.py)), one entry point. Every task wraps an
existing frozen component; none re-implements attack or defence logic.

```mermaid
flowchart LR
    R[(registry.json<br/>tracks · tasks · metrics)] --> S{task supported?}
    S -- no --> U[UNSUPPORTED]
    S -- yes --> Q{requirements met?<br/>licensed data · Ollama · isolated env}
    Q -- no --> BL[BLOCKED]
    Q -- yes --> X[run executor in a scratch dir]
    X --> E{outcome}
    E -- exception / integrity violation /<br/>tracked file modified --> F[FAILED]
    E -- evidence absent --> N[NOT_EVALUABLE]
    E -- metrics --> C[COMPLETED]
    U & BL & F & N & C --> A[[results.json<br/>per-task denominators,<br/>provenance, hold-out run count]]
```

A proportion is reported only as numerator/denominator; a zero denominator is `NOT_EVALUABLE`,
never 0. There is no single overall score.

| Track | Tasks |
|---|---|
| attack_validity | attack-population coverage · poison admission rate · MPBench inapplicable classes (UNSUPPORTED) |
| defence_detection | B0–B8 ablation on the frozen corpus · B9/B12 on published held-out splits |
| propagation_containment | seven-attack footprints · benign baseline · propagation rate (needs Ollama) |
| sleeper | directive-evasion study · activation shape (needs the isolated Mem0 environment) |
| attribution | origin, false attribution, path fidelity, lineage ambiguity |
| provenance_integrity | ledger tamper evidence · evaluator-only field rejection |
| data_integrity | full leakage audit (needs processed corpora) · LoCoMo-only leakage checks · sha256 of all 18 frozen hold-outs |

```bash
python -m mambench list
```
```bash
python -m mambench run --smoke --strict
```
```bash
python -m mambench run --all
```

Each run writes `mambench_results/<timestamp>-<commit>/` (gitignored), never overwrites an earlier
run, and appends to `holdout_ledger.jsonl` so repeated evaluation of a held-out split is visible.

## Tech stack

| Layer | Tools |
|---|---|
| Language and tests | Python 3.11, pytest, GitHub Actions |
| Models (local) | Ollama: qwen2.5:7b (judge/detector), llama2 (agent), phi3:mini, mistral, llama-guard3; pins in `phase17/OLLAMA_MODEL_PINS.md` |
| Models (remote, optional) | Gemini API (independent judge) |
| Embeddings and classifiers | sentence-transformers all-MiniLM-L6-v2, ProtectAI deberta-v3 prompt-injection, PyTorch, transformers |
| Memory foundations | clean agent (mock Mem0), Mem0 2.0.19 with Qdrant, A-mem-sys (isolated interpreters, `phase17/ISOLATED_ENVIRONMENTS.md`) |
| Analysis | numpy, scipy, scikit-learn, networkx, python-docx, matplotlib |

Provenance records are hash-chained so edits, deletions, reordering and truncation are detectable:
$h_i = \mathrm{SHA256}\bigl(\mathrm{canon}(r_i \cup \{\mathit{seq}=i,\ \mathit{prev}=h_{i-1}\})\bigr)$, $h_{-1}$ = genesis, with
the head stored separately (optionally HMAC-keyed).

## Running it

```bash
pip install -r requirements.txt
```
```bash
python scripts/ci/fetch_licensed_data.py
```
```bash
make regression
```

`make regression` runs exactly what CI runs: Phases 3–16, attribution and `tests/`; the full
Phase 17 suite; and the benchmark checks. `fetch_licensed_data.py` downloads LoCoMo from pinned
upstream commits and checks it against the sha256 in `data/metadata/dataset_manifest.json`; CI
does the same to run the held-out split evaluations, and installs the hashed Linux lock
`requirements-ci.txt`. CI (`.github/workflows/tests.yml`) runs on `main`,
`remediation/**` and pull requests, with no live model (`OLLAMA_BASE_URL` points at a closed
port), so LLM-judge decisions come from the committed caches. Live experiments need Ollama with
the pinned models, and some need the isolated Mem0/A-MEM environments; see
`phase17/RUNNING_THE_PIPELINE.md`.

## Known limitations

- **Gap 3 is not closed (33.8%).** No pre-registered operating point detects implicit sleepers
  while keeping legitimate conditional notes under the 10% limit; attacks relayed through the
  user pass every provenance defence (0/24).
- **Small local models.** Agents and judges are 7–8B local models; harm levels depend on the judge,
  so reductions are more reliable than absolute levels.
- **Reconstructions.** The attacks are reconstructions of published techniques, not the authors'
  code; AgentPoison in particular is weaker than the original.
- **Licensed data is not redistributed.** `data/raw/` is gitignored; CI fetches only LoCoMo, pinned
  and digest-verified. The full four-check leakage audit also needs the processed LongMemEval,
  MSC and Conversation Chronicles corpora (about 3.6 GB, and MSC has no explicit licence), so on
  CI it reports BLOCKED and two of its four checks run as a separate task.
- **Reproducibility is not bit-exact for live runs.** Model sampling varies (repeated agent runs
  differ by about one case in 150); offline tasks and cached-judge evaluations are deterministic.
- `requirements-lock.txt` is a Windows/CUDA freeze of the development machine; CI and Linux users
  install `requirements-ci.txt` (exact versions with hashes, Linux, Python 3.11).

## Repository map

| Path | Contents |
|---|---|
| `phase3/` | frozen victim agent, memory foundations, dataset candidates |
| `phase4/` | the seven attacks and the shared attack contract |
| `phase5/`, `attribution/` | instrumentation, event ledger, attribution layer |
| `phase6/`–`phase15/` | defences, propagation, sleeper, risk composition, GNN/GLN, metrics, utility |
| `phase17/` | ablation, generalisation, hold-outs, defence programmes v2–v7 |
| `mambench/` | unified benchmark registry, schema, runner and tests |
| `docs/`, `paper/` | phase reports, figures, specifications, manuscript sources |
| `data/metadata/` | dataset manifests and freeze records |

Data licences and annotation provenance: [`DATA_LICENSING_AND_ANNOTATION_AUDIT.md`](DATA_LICENSING_AND_ANNOTATION_AUDIT.md).
