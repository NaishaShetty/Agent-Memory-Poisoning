# MAMBench — Research Methodology Draft
## Phases 1–2: Dataset and Benchmark Foundations

*First-draft methodology, prepared for professor review. Not a final paper section.
Reconstructed from the project repository's own code, manifests, validation reports,
and documentation — not from an idealized description of what a benchmark of this
kind should do. Uncertain or undocumented points are marked [TO VERIFY].*

---

## 1. Research Methodology Overview

MAMBench (Memory-Agent Memory-poisoning Benchmark) is being developed to study
memory-poisoning attacks against LLM agents with external, persistent memory. Before
any agent architecture, memory lifecycle logic, or attack methodology could be
introduced, the project first had to establish a **verified, honestly-documented
data foundation** — real conversational memory datasets, cleaned and normalized
into a common representation, with every fact about their provenance, quality, and
availability made explicit rather than assumed.

Phases 1 and 2 together constitute this foundation-building stage:

- **Phase 1** identified, acquired, and registered the candidate datasets and
  resources the project would need across its full lifecycle (not only memory data,
  but also task-workload, attack, sleeper, and evaluation resources), and produced
  the first cleaned, quality-classified, provenance-preserving processed output for
  the datasets intended as memory substrate.
- **Phase 2** took Phase 1's processed output for the four core memory datasets and
  built a series of additive, validated layers on top of it — a unified schema, a
  temporal-normalization policy, a benchmark-role organization layer, a
  reproducibility-identity layer, cross-layer substrate validation, and a final
  freeze/acceptance gate — without ever regenerating, reprocessing, or silently
  altering the Phase 1 output underneath.

**The guiding methodological principle across both phases is separation of concerns
between raw source data, derived/processed artifacts, and downstream experimental
infrastructure**, each layered so that later phases can consume an artifact without
needing to trust (or re-verify) how it was produced. This is documented explicitly
in the project's own layering model (`data/raw` → `data/processed`/`interim` →
approved Phase 2 inputs → future benchmark-generated data), enforced by both
directory convention and automated validation checks, not by prose alone.

**What Phases 1–2 establish, stated narrowly**: a verified inventory of relevant
resources, and — for four datasets specifically — a cleaned, schema-unified,
temporally-normalized, role-classified, reproducibility-tracked corpus of
1,266,194 conversational memory records. They do **not** establish reproducibility
in the strongest possible sense (a dependency lockfile and automatic code-state
stamping remain open items, discussed in Section 5), and they do not establish
anything about how this substrate will later be used by an agent, a memory
lifecycle system, or an attack methodology (Section 9).

---

## 2. Phase 1 — Dataset and Benchmark Foundations

### 2.1 Dataset Identification

Phase 1 identified and researched a total of **28 resources** [TO VERIFY: the
registry module's own docstring says "27 resources," while both the generated
manifest and the direct entry count agree at 28 — this is recorded in the
project's own issue log as a stale-by-one code comment, not a data
inconsistency; the machine-generated count (28) is treated as authoritative
here], spanning five categories:

- **Memory / conversational data** (4): LoCoMo, LongMemEval, Multi-Session Chat
  (MSC), Conversation Chronicles — the datasets intended as the project's core
  long-term-memory substrate.
- **Task / domain workload datasets** (9): API-Bank, ToolBench, StrategyQA,
  WebShop, SWE-bench Verified, tau-bench, tau2-bench, EHRAgent, MIMIC-III/eICU —
  intended for later agent task-execution scenarios.
- **Sleeper / dormant-poisoning resources** (2): "Hidden in Memory" and a
  "Sleeper Dataset Generator" — intended for later delayed-trigger poisoning
  research.
- **Memory-poisoning attack resources** (6): AgentPoison, MINJA, DSRM,
  MemoryGraft, FARMA, MPBench — attack methodologies from the literature,
  identified and specified but explicitly not implemented or executed in Phase 1.
- **Security-benchmark / evaluation / defense resources** (7): MemSecBench,
  MEMSAD, MemAudit, A-MemGuard, ASB, AgentDojo, InjecAgent — comparison and
  evaluation resources for later phases.

Each resource's inclusion is justified by a stated `research_purpose` field
recorded at identification time (e.g. LoCoMo: "primary long-term conversational
memory substrate with native multi-hop/temporal QA task structure"; DSRM: an
attack "targeting RAG-based tool-using agents" via disguised adversarial
reasoning). These stated purposes are carried through unchanged from Phase 1's
own registry and are not re-derived or reinterpreted in this document.

For each resource, Phase 1 recorded — where verifiable — its source (URL/paper
citation), license, version or revision (explicitly `"unavailable"` where the
publisher provides no version tag, e.g. LoCoMo, LongMemEval, and Conversation
Chronicles), and an honest, verified acquisition/implementation state (e.g.
"code publicly available but not cloned" is recorded as a distinct fact from
"no public implementation could be found"). Resources for which no legitimate
public artifact could be located (several of the attack and security-benchmark
resources) are recorded as such rather than omitted — their absence from local
storage is itself part of the documented record.

**Inclusion/exclusion decisions were dataset-specific and disclosed, not
uniform.** Examples actually recorded in the repository:
- LongMemEval's large `m_cleaned` raw variant (~2.7GB) was deliberately not
  acquired, for repository-size reasons — the `oracle` and `s_cleaned` variants
  were judged sufficient for the approved foundation.
- Conversation Chronicles' raw episode count (200,000) was judged to be roughly
  50× larger than the other three core datasets combined; a documented, seeded
  reservoir sample (10,000/2,000/2,000 of 160,000/20,000/20,000
  train/valid/test episodes) was taken instead of processing the dataset in
  full, on the stated methodological principle that "multiple sources should
  prevent overfitting to one dataset's structure, not entrench one."
- MIMIC-III/eICU and the credentialed portions of EHRAgent were not acquired at
  all, because they require PhysioNet credentialing this project did not have
  — recorded as a genuine external access constraint, not a processing gap.

[PROFESSOR REVIEW: the repository does not contain a single narrative document
explaining the original *selection criteria* for these 28 resources as a set
(e.g., why these four particular memory datasets and not others) — the
`research_purpose` field on each registry entry states each resource's intended
role, but a higher-level justification of "why these four together constitute
an adequate memory foundation" is not present as a standalone document and would
need to be reconstructed, if desired, from the project's separate
`Methodology.pdf`/literature-review materials, which were not consulted for
this draft. Marked [TO VERIFY].]

### 2.2 Dataset Registry / Inventory

Every identified resource was catalogued in a single, machine-generated
**resource registry** (`preprocessing/registry.py` → `data/metadata/resource_registry.json`,
registry schema version `1.0.0`), independent of the resource's category or
current availability. Each registry entry records:

- a stable `resource_id` and human-readable `name`;
- its `category` (one of `memory_data`, `task_workload`, `sleeper`, `attack`,
  `security_benchmark`);
- its `research_purpose`;
- separate status fields for **Phase 1 status** (`PROCESSED` /
  `PREPARED` / `INSPECTED` / `OPTIONAL_PENDING_ACCESS` / `INACCESSIBLE` /
  `NOT_SUITABLE` / `DEFERRED_WITH_JUSTIFICATION`), **acquisition status** (a free-text
  description of what was actually obtained, e.g. "code available, not cloned"),
  and **preprocessing status**;
- `version_or_revision`, `access_and_license`, `local_path` (if any),
  `source_reference`, a `reproducibility` note (how the resource could be
  regenerated/re-acquired), `limitations`, and `intended_later_phase`.

**Status vocabulary is deliberately narrow and non-overlapping** — the registry's
own documentation states explicitly that "a resource can be `INSPECTED` (Phase 1
status) while its acquisition status is 'code available, not cloned'" and that
this must never be conflated with "processed" or with "implemented." This
distinction (`acquired ≠ organized ≠ prepared ≠ implemented ≠ experimentally
activated`) recurs throughout both Phase 1 and Phase 2 and is treated in the
project's own documentation as an explicit governing principle, not an
incidental detail.

Identity stability across the pipeline is maintained through a **deterministic
memory-record identifier** (`preprocessing/io_utils.py: deterministic_id()`) —
a SHA-256 hash computed over each record's ordered provenance tuple — so the
same source record always produces the same identifier across repeated runs,
without depending on file order or run timestamp.

### 2.3 Dataset Categorization

Phase 1 established exactly the five categories enumerated in 2.1
(`memory_data`, `task_workload`, `sleeper`, `attack`, `security_benchmark`),
using this exact terminology throughout the registry and all downstream Phase 2
documents. Each resource maps to exactly one category at the registry level
(a separate, later Phase 2.4 process — Section 3.3 below — reclassifies these
same categories into benchmark-facing "roles," a distinct downstream concept
built strictly on top of, not replacing, this Phase 1 categorization).

### 2.4 Dataset Provenance and Integrity

For the four core memory datasets specifically, Phase 1's processing pipeline
(`python -m preprocessing.run_all`) produced, for every retained memory record, a
`provenance` object recording its originating dataset, source file, and source
record identifier, alongside the deterministic identifier described above.

**Integrity is checked, not assumed.** Every raw source file for the core
datasets is SHA-256-hashed at manifest-build time (`data/metadata/dataset_manifest.json`),
recomputed from disk rather than copied from an external claim. A dedicated test
(`tests/test_phase2_boundary.py::test_raw_files_unchanged_since_dataset_manifest_was_generated`,
confirmed present in the repository) re-hashes these files on every test run and
fails if a single byte has changed, providing an ongoing, automated guarantee
that raw source data remains immutable after acquisition.

**Version/revision information is recorded honestly, including its absence.**
Where the upstream publisher provided no version tag or pinned commit (LoCoMo,
LongMemEval, Conversation Chronicles), this is recorded explicitly as
`"unavailable"` rather than inferred or left blank. MSC's version (`v0.1`) was
recoverable from the ParlAI build script and is recorded as such.

### 2.5 Phase 1 Validation

Phase 1's own validation (`data/reports/phase1_validation_report.json`) ran ten
named checks against the full processed corpus (1,266,194 memory records,
2,986 task records at that point in the pipeline): unique memory IDs, no
cross-dataset ID collisions, valid source references, valid provenance, no
broken task-evidence links, session/conversation consistency, valid event
ordering, encoding correctness, schema consistency, and no train/test leakage.

**Result, exactly as recorded**: nine of ten checks `PASS`. One check,
`encoding_correctness`, **FAILs** — two LongMemEval records contain U+FFFD
(mojibake/replacement) characters, a defect present in the raw source file
itself (verified at the byte level in a later remediation pass — see Section
2.6 below) rather than introduced by Phase 1's own processing. The report's own
`overall_status` field is recorded as `"FAIL"` as a direct consequence of this
one check — the project's documentation explicitly does not overwrite or
soften this into a passing status; it is instead carried forward and
explicitly labeled `PASS WITH ISSUES` in later Phase 2 documents (Section 3.7).

**This distinction matters methodologically**: Phase 1 validation checks
structural/statistical properties of the processed corpus (uniqueness,
referential integrity, schema conformance, encoding) — it is not itself a claim
about the scientific validity or fitness-for-purpose of the datasets, and the
project's own documentation is explicit that these are separate questions.

### 2.6 Phase 1 Limitations

The following limitations were identified during Phase 1 (and, in several
cases, further investigated and formalized in a documented Phase 2.1 remediation
pass — see the corresponding citations):

- **Two LongMemEval records carry an unrepaired encoding defect** (U+FFFD
  replacement characters), traced to the raw source file itself. These records
  are deliberately not "fixed" (repairing destroyed characters would require
  guessing at lost content, which the project's data-integrity rules forbid) and
  are instead formally excluded from any trusted-clean-memory baseline via a
  provenance-exceptions registry (`data/metadata/longmemeval_provenance_exceptions.json`).
- **LongMemEval's `m_cleaned` raw variant was never acquired** (repository-size
  reasons), limiting later phases to the `oracle`/`s_cleaned` haystack scale
  unless a separate acquisition is performed.
- **444 of 1,986 LoCoMo QA instances (~22%) lack an answer field.** A later
  remediation pass confirmed these are category-5 adversarial questions with no
  ground-truth answer by the source dataset's own design, not an unexplained
  processing gap, and built an explicit reconciliation layer distinguishing
  answer-evaluable from non-evaluable QA instances.
- **MSC's dataset-level license is not explicitly published** by its source (only
  the ParlAI framework code's MIT license is confirmed) — recorded as an open
  question for any future redistribution/publication use, not assumed permissive.
- **93% of Conversation Chronicles' raw episodes were deliberately excluded**
  via the documented sampling cap described in 2.1 — later analyses must not
  describe the processed set as the complete source dataset.
- **No version-control system was in use during Phase 1**, meaning no commit or
  code-content hash originally tied a given processed output to an exact code
  state. [TO VERIFY / PROFESSOR REVIEW: this gap is recorded in the project's
  own `REPRODUCIBILITY_REPORT.md` as resolved in a later Phase 2.1 remediation
  pass, which is arguably a Phase 2, not Phase 1, activity — included here only
  because the underlying gap originates in Phase 1's own process.]

None of these limitations are presented in the project's own documentation as
blocking; each is explicitly disclosed, and the project's stated methodological
stance throughout is that a documented limitation is preferable to a silently
"cleaned up" one.

---

## 3. Phase 2 — Dataset Preparation and Benchmark Infrastructure

Phase 2 is organized into the project's own real subphases, 2.1 through 2.7,
each adding exactly one additive layer on top of Phase 1's frozen output. No
subphase regenerates or reprocesses an earlier subphase's output; each is
validated independently and then re-validated, fresh, by later subphases (most
comprehensively in 2.6).

### 3.1 Phase 2.1 — Data Boundary and Input Approval

**Objective**: formally mark which of Phase 1's 28 registered resources are
approved to be used as inputs to Phase 2's own construction work, and make the
layering between raw data, Phase 1 output, and approved Phase 2 input explicit
and enforced.

**Inputs**: Phase 1's resource registry and its processed output for the four
core datasets.

**Processing methodology**: Phase 2.1 defines a four-layer model — (1) raw
source data, immutable; (2) Phase 1 derived artifacts, frozen and read-only
going forward; (3) officially approved Phase 2 inputs, a new manifest layer;
(4) future benchmark-generated data, reserved, not yet populated. It adds one
new artifact, `data/metadata/phase2_input_manifest.json`, giving every one of
the 28 resources an explicit `phase2_status` (one of
`PHASE2_INPUT_APPROVED`/`PREPARED`/`INSPECTED`/`CONDITIONALLY_AVAILABLE`/
`UNAVAILABLE`/`UNVERIFIED`/`NOT_GENERATED`) and a boolean `phase2_input_approved`.

**Outputs**: `phase2_input_manifest.json`. **Only the four core memory
datasets — LoCoMo, LongMemEval, MSC, Conversation Chronicles — are marked
`phase2_input_approved: true`.** This is documented as a deliberate, narrow
scope decision: approving the other 24 resources here would conflate "this
resource exists and is recorded" with "this resource is cleared for the
specific artifact Phase 2.1 is chartered to produce," a distinction the
project's documentation treats as important to keep explicit rather than
implicit.

**Validation**: `tests/test_phase2_boundary.py` asserts the approved-resource
set is exactly the four core IDs, that no `attack`/`sleeper`-category resource
is ever approved regardless of its Phase 1 status, and re-hashes raw files to
confirm Layer 1 immutability (Section 2.4 above).

**Reproducibility controls**: manifest generation is a pure, deterministic
function of the registry and a supplied timestamp; a dedicated test
(`test_manifest_generation_is_deterministic_given_fixed_timestamp`, confirmed
present) verifies this directly.

### 3.2 Phase 2.2 — Unified Memory Record (UMR)

**Objective**: define a single common schema so that later components never
need to know which of the four source datasets a given memory record came
from.

**Inputs**: Phase 1's already-processed `data/processed/<dataset>/memory_records.jsonl`
for the four core datasets — never raw source files.

**Processing methodology**: every conversational turn from the four datasets is
mapped, one-to-one, into a Unified Memory Record (schema version `1.1.0` at the
time of this draft — bumped additively by Phase 2.3, see 3.3.1). The UMR reuses
Phase 1's deterministic memory identifiers and quality classification verbatim
rather than reimplementing them. Each field that could plausibly be absent,
uncertain, or not-yet-computed is paired with an explicit `field_status` value
drawn from two combined vocabularies — **positive origins**
(`SOURCE_PROVIDED`/`BENCHMARK_GENERATED`/`INFERRED`/`MODEL_PREDICTED`) and
**absence reasons** (`NOT_AVAILABLE`/`NOT_APPLICABLE`/`UNRESOLVED`/`NOT_EVALUATED`)
— so a reader never has to guess whether a value came from the source dataset
or was constructed by MAMBench itself. Fields reserved for later phases
(`derivation_parents`, `retrieval_history`, `propagation_history`,
`trust_score`, `security_state`, `poison_status`, `embedding`) are present in
the schema with defined semantics but are populated with `null`/`[]` and an
honest absence status in Phase 2.2 — never with a fabricated placeholder value.

**A specific, disclosed design decision**: LoCoMo's QA fields (`answer`,
`adversarial_answer`, `canonical_answer`, `question`, etc.) are deliberately
never embedded inside a memory record — they are kept in a physically separate
file (`data/processed/locomo/qa_reconciled.jsonl`), joinable only by
`(source_dataset, conversation_id)`. This is stated in the project's
documentation as a deliberate methodological choice so that "a memory record
may be valid even if an associated QA instance is not eligible for a particular
evaluation metric" can never be silently lost by merging the two record types.

**Outputs**: `data/processed/unified_memory/<dataset>/memory_records.jsonl` for
all four datasets, sitting alongside (not replacing) Phase 1's own output.

**Validation**: a cross-dataset validator streams all four datasets' UMR
output and checks schema conformance, identifier uniqueness within and across
datasets, `source_dataset` consistency, vocabulary conformance for
`admission_status`/`field_status`, the invariant that no `QUARANTINED` record is
ever marked `trusted_clean_memory: true`, and that total record counts match
Phase 1's own processed output exactly. Recorded result: **PASS on every check,
1,266,194 total records, zero collisions** (`data/reports/phase2_2_unified_memory_validation_report.json`).

**Reproducibility controls**: the mapping is a pure function of Phase 1's own
frozen output; no statistical rebalancing across datasets is performed (the
project's documentation states this explicitly — "the four datasets' natural
size/composition differences... are preserved as-is").

### 3.3 Phase 2.3 — Temporal Normalization

**Objective**: give every UMR record a common, non-fabricating temporal
representation, since the four source datasets encode "when" in four mutually
incompatible ways (two provide a real absolute per-session timestamp in
free-text form; two provide only a relative inter-session gap description, or
nothing for the first session).

**Inputs**: Phase 2.2's UMR output (schema `1.0.0` at that point).

**Processing methodology**: two new fields are added — `normalized_timestamp`
(a real, deterministically-reparsed absolute ISO-8601 time, populated only when
a genuine source-absolute timestamp exists) and `temporal_provenance` (one of
`source_absolute`/`source_relative`/`benchmark_assigned`/`unknown`, recording
which kind of real-world temporal claim the record actually supports). A
previously-reserved field, `benchmark_timestamp`, is populated **only** when no
real absolute time is available, using a documented, deterministic formula
based on `(session_ordinal, event_order)` anchored at the Unix epoch as a
human-legible "this is synthetic" sentinel — the project's documentation states
explicitly that "benchmark-assigned timestamps are analytical constructs
created by MAMBench and must not be interpreted as source-observed
timestamps," and that the authoritative machine-readable signal for this is
always the `temporal_provenance` field, not the value's format.

**A specific per-dataset mapping** (recorded in the project's own documentation
and machine-readable policy table) governs which datasets receive
`source_absolute` treatment (LoCoMo, LongMemEval) versus `source_relative`
treatment with a synthetic `benchmark_timestamp` (MSC, Conversation
Chronicles).

**Outputs**: the same UMR files, additively extended; UMR schema version
bumped to `1.1.0` to reflect the additive (not breaking) change; the temporal
policy itself is versioned independently (`2.3.0`).

**Validation**: seven named checks against the regenerated corpus — vocabulary
conformance, no accidental fabrication (a `source_absolute` record never also
carries a `benchmark_timestamp`), monotonic event/session ordering as each
file is streamed, determinism, no silent invention of missing temporal
information, no two identical source-timestamp strings parsing to different
normalized values, and well-formedness across all four datasets. Recorded
result: **PASS on every check**, run against the full 1,266,194-record corpus;
Phase 2.2's own validator was also re-run against the regenerated corpus and
confirmed still `PASS`.

**Reproducibility controls**: every function in the temporal-normalization
module is a pure function of record-level inputs and fixed module constants
(no wall-clock read, no randomness) — verified both by unit tests and by a
substrate-level check that recomputes temporal fields from a 200-record-per-dataset
sample and confirms the result matches what is stored on disk.

### 3.4 Phase 2.4 — Benchmark-Level Resource Organization

**Objective**: answer, in one enforced place, which of the project's 28
tracked resources constitute memory, workload, attack, sleeper, or evaluation
resources — and make it structurally difficult for an attack or sleeper
resource ever to be treated as clean memory data.

**Inputs**: Phase 1's resource registry (identity/provenance/category) and
Phase 2.1's input-approval manifest (availability/approval status) — both read,
neither modified.

**Processing methodology**: this phase is explicitly documented as a **join and
classification layer, not a new data source.** It reads both upstream
documents, classifies each resource's existing Phase-1 `category` into exactly
one of five benchmark **roles** (`memory`/`workload`/`attack`/`sleeper`/`evaluation`)
via a fixed, total, 1:1 mapping, and writes the join as a new manifest. It
mutates neither of the two documents it reads, and it does not reprocess or
rescore any dataset. A dedicated invariant — enforced, not merely asserted —
requires that the `memory` role be **exactly** the same four datasets already
approved in Phase 2.1, in both directions: a resource in the approved memory
set must be classified `memory`, and a resource classified `memory` must be in
the approved set. The project's test suite includes a synthetic test that
deliberately corrupts the role-mapping table to confirm this invariant is
actually enforced by the code, not merely true of today's data by coincidence.

Each organized entry also carries a computed `implementation_status`
(`local_copy_present` / `public_code_available_not_locally_implemented` /
`specification_only_no_public_implementation_found` / `unresolved`), derived by
a single deterministic rule from each resource's own existing acquisition text
— never a per-resource hardcoded judgment. The project's documentation gives a
worked example (DSRM: role `attack`, `specification_only_no_public_implementation_found`,
no local path, not Phase-2-input-approved) as an illustration that a resource's
role and its actual implementation readiness are tracked as genuinely
independent facts.

**A specific methodological point directly relevant to how this phase should
be described**: Phase 2.4 is explicitly a **logical**, not physical,
organization layer. It does not move, copy, or symlink any dataset file into a
new directory tree. The 1,266,194 existing UMR records remain exactly where
Phase 2.2 wrote them; the benchmark-role manifest instead references each
resource by its already-existing `resource_id`/`local_path`, so a reader
obtains the logical grouping and the real on-disk path from the same manifest
entry, without either being duplicated. **Physical dataset storage, metadata,
manifests, and logical benchmark role are four separate concepts kept
separate throughout** — this document does not describe any dataset as having
been "moved into" a benchmark directory, because that did not happen.

**Outputs**: `data/metadata/benchmark_resources.json` (organization version
`1.0.0`), stating role counts, per-resource role/status, and a summarized
`umr_integrity` block (itself read from Phase 2.2/2.3's own already-written
validation reports, not recomputed by scanning the corpus again).

**Validation**: twelve named checks, re-running Phase 2.2's and 2.3's
validators fresh (not merely reading their last-written reports) so a single
Phase 2.4 run can answer "did this break anything earlier." Recorded result:
**PASS overall — 28/28 resources organized**, role counts
`{memory: 4, workload: 9, attack: 6, sleeper: 2, evaluation: 7}`.

**Reproducibility controls**: the organization-building function is a pure
function of its two input documents plus a supplied timestamp; determinism is
verified both by direct unit tests and by the validator building the
organization twice and comparing.

### 3.5 Phase 2.5 — Reproducibility Metadata

**Objective**: answer, for every one of the 28 resources, "exactly which
source version/snapshot, MAMBench preparation pipeline, schema, temporal
policy, configuration, and seed produced this artifact, and could someone else
reproduce it?" — a question the project's documentation states is distinct
from (and does not follow automatically from) resource identity, role, or
status.

**Inputs**: `benchmark_resources.json` (Phase 2.4), which itself already
chains through the registry and the Phase 2.1 manifest — read only, not
re-derived.

**Processing methodology**: for every resource, a `canonical_identity` is
computed from its source version/snapshot, MAMBench preparation version,
relevant schema/policy versions, a configuration identifier (a content hash of
`pipeline_config.yaml`), and the pipeline seed — deliberately excluding any
wall-clock generation timestamp or local filesystem path, so the canonical
identity is machine- and run-independent by construction. A deterministic
`canonical_identity_hash` is derived from this. For the four resources an
actual preparation pipeline has run against, an additional `artifact_identity`
block is recorded; for resources with no prepared artifact (e.g. attack
specifications with no local implementation), this is explicitly marked
`not_applicable_no_prepared_artifact` rather than omitted or fabricated.

Every version value in the resulting manifest is read from its single existing
source-of-truth constant (e.g. the UMR schema version is read from
`unified_schema.py`, never re-typed as an independent literal) — the project's
documentation frames this explicitly as preventing version drift between
documents that describe the same fact.

**Outputs**: `data/metadata/reproducibility_manifest.json` (manifest version
`1.0.0`).

**Validation**: [TO VERIFY — the specific named checks and PASS/FAIL result for
Phase 2.5's own validator were not directly located as a separate report file
during this reconstruction; Phase 2.6's own cross-validation (3.6 below)
re-runs and reports on it, and that combined result was directly verified.
The professor-facing version of this draft should confirm whether a
standalone `phase2_5_reproducibility_validation_report.json`-equivalent
exists and, if so, cite its specific check count directly.]

### 3.6 Phase 2.6 — Cross-Phase Substrate Validation

**Objective**: validate claims that no single earlier-phase validator could
express on its own — whether the four independently-built layers (UMR,
temporal policy, resource organization, reproducibility metadata) agree with
each other, not merely whether each is internally self-consistent.

**Inputs**: the real, full corpus and all Phase 2.2–2.5 manifests — read only.

**Processing methodology**: Phase 2.6 does not reimplement any earlier
validator's logic; it re-runs each one fresh (not from a cached report) and
additionally checks cross-manifest agreement — e.g., that the same
`resource_id` set and the same `primary_role`/`source_reference`/`phase2_status`/
`phase2_input_approved` values appear consistently across all four manifests;
that every layer stating a copy of a shared version number (UMR schema,
temporal policy, organization version) states the identical value; that
record counts agree across three independently-computed sources (a fresh
corpus stream, the organization layer's summary, and the reproducibility
manifest's summary) rather than one layer merely repeating another's stale
number; and an explicit scan of the `preprocessing/` codebase for any function
or class definition whose name implies poisoning, attack, sleeper,
propagation, lifecycle, defense, mitigation, containment, attribution, or
GNN/GLN semantics — confirming, structurally, that no such implementation
exists yet, rather than relying on a keyword search that would also flag
legitimate role-name constants and reserved schema fields.

**Outputs**: `data/reports/phase2_6_benchmark_substrate_validation_report.json`.

**Validation result, as recorded**: **29 named checks, all `PASS`.**

**A specific, disclosed performance/scope decision**: raw-file integrity
re-checking is bounded (files under 5MiB are rehashed on every run; larger
files, already SHA-256-verified at acquisition time, are checked by file size
only on subsequent runs) — the project's documentation states this explicitly
as a deliberate trade-off, not a silently weaker guarantee.

### 3.7 Phase 2.7 — Acceptance and Freeze

**Objective**: re-confirm the entire Phase 2 substrate exactly once more, then
compute and record a single canonical identity for the *whole* Phase 2 state,
establishing a tripwire against future silent modification.

**Inputs**: Phase 2.6's validator, invoked fresh one final time.

**Processing methodology**: a single SHA-256 hash is computed over an
explicit, documented set of inputs — the pipeline/schema/policy/organization/
reproducibility/substrate-validation/freeze version strings, the configuration
identifier, the memory-foundation dataset identifiers and per-dataset record
counts, the resource-role counts, and all 28 resources' own individual
canonical-identity hashes (from Phase 2.5) — explicitly excluding generation
timestamp and any local filesystem/machine identity, mirroring the same policy
Phase 2.5 already applied per-resource.

**Outputs**: `data/metadata/phase2_freeze_manifest.json` (freeze version
`2.7.0`), which does not duplicate the content of the four manifests beneath
it — it references them by path and states the whole-Phase-2 canonical
identity and freeze status on top.

**The project's own recorded overall status at freeze is explicitly `PASS WITH
ISSUES`** — the same honest status established at the point each underlying
issue (Section 2.6) originated, not silently upgraded to a clean `PASS` by the
freeze process.

**Freeze policy, as documented**: UMR semantics/schema, memory-foundation
membership and IDs, temporal semantics/policy, benchmark resource roles,
reproducibility metadata semantics, and the Phase 2 manifests themselves are
frozen — a later phase may read this substrate and build derived experimental
artifacts on top of it, or create new data outside it, but must not silently
modify any of the above. The freeze is documented explicitly as "a tripwire,
not a filesystem lock" — no file permission is changed; any future accidental
or deliberate change to the frozen state would be detectable by recomputing
the canonical hash and comparing it against the one recorded at freeze time.

---

## 4. Dataset-to-Benchmark Mapping

The path from a raw source dataset to something a later phase can actually
consume follows the layered chain established across Phases 1–2:

```
SOURCE DATASET (data/raw/<id>/, immutable, hash-verified)
        |
        v
REGISTRY / METADATA  (Phase 1: resource_registry.json — identity, category,
                       Phase 1 status, provenance)
        |
        v
PHASE 2 INPUT APPROVAL (Phase 2.1: phase2_input_manifest.json — which
                          resources may be used as Phase 2 inputs)
        |
        v
PREPARATION / UNIFIED SCHEMA (Phase 2.2/2.3: data/processed/unified_memory/ —
                                 what the memory record IS, temporally normalized)
        |
        v
BENCHMARK ROLE ORGANIZATION (Phase 2.4: benchmark_resources.json — which of
                                five roles this resource plays; a LOGICAL
                                grouping, not a physical relocation)
        |
        v
REPRODUCIBILITY IDENTITY (Phase 2.5: reproducibility_manifest.json — exactly
                             which version/config/seed produced this artifact)
        |
        v
CROSS-LAYER VALIDATION + FREEZE (Phase 2.6/2.7: one canonical, tripwired
                                    Phase 2 identity)
        |
        v
DOWNSTREAM EXPERIMENTAL AVAILABILITY (later phases: read-only consumption of
                                         the frozen substrate)
```

**Physical storage, metadata, manifests, and logical role are kept as four
distinct concepts throughout this chain, never collapsed into one.** A dataset
record's physical bytes live in exactly one place
(`data/processed/unified_memory/<dataset>/memory_records.jsonl`) from Phase 2.2
onward; every later layer (role, reproducibility identity, freeze status)
annotates that same record set by reference, rather than duplicating or
relocating it.

| Layer | What it answers | Canonical artifact |
|---|---|---|
| Registry | What is this, and where from? | `resource_registry.json` |
| Phase 2 input approval | Is this cleared for Phase 2 use? | `phase2_input_manifest.json` |
| UMR + temporal | What is a memory record, and when did it happen? | `data/processed/unified_memory/<dataset>/memory_records.jsonl` |
| Benchmark organization | What job does this resource do? | `benchmark_resources.json` |
| Reproducibility | Exactly which version/config produced this? | `reproducibility_manifest.json` |
| Freeze | Is the whole Phase 2 state internally consistent and locked? | `phase2_freeze_manifest.json` |

---

## 5. Reproducibility Methodology

The following reproducibility mechanisms are actually implemented and verified
in the repository, and only these are claimed:

- **Deterministic record identifiers** — SHA-256 over each record's ordered
  provenance tuple, verified collision-free across and within all four datasets
  at full corpus scale.
- **A fixed master seed** (`config/pipeline_config.yaml: seed: 20260101`), the
  only source of randomness in the Phase 1–2 pipeline, used for Conversation
  Chronicles' deterministic reservoir sample.
- **Raw-file integrity via recomputed SHA-256 checksums**, re-verified on every
  test run for files below a defined size threshold (Section 3.6).
- **Explicit schema and policy versioning** at every layer (UMR schema `1.1.0`,
  temporal policy `2.3.0`, organization version `1.0.0`, reproducibility
  manifest version `1.0.0`, freeze version `2.7.0`), each read from a single
  source-of-truth constant rather than independently re-declared.
- **A machine-independent canonical identity hash**, both per-resource (Phase
  2.5) and for the whole Phase 2 state (Phase 2.7), deliberately excluding
  generation timestamp and local filesystem paths.
- **A local Git repository**, initialized during a Phase 2.1 remediation pass,
  tying a specific commit to a specific recorded data/metadata state — the
  project's own documentation states this resolves an originally-identified gap
  ("no code-state identity") but explicitly notes two related items remain
  open (see Limitations below).

**Reproducibility claims this project does NOT make, and are not implemented**:
- **No dependency lockfile.** `requirements.txt` uses `>=` version ranges; no
  `pip freeze` snapshot or lockfile is captured anywhere in the repository.
- **No automatic code-state stamping.** The Git commit hash is not
  automatically written into any generated report or the `PIPELINE_VERSION`
  string — recovering "which exact code produced this data" requires a human
  to manually correlate a commit with a manifest's content.
- **No independently re-executed full pipeline run** as evidence of
  determinism for the core dataset pipeline — determinism is demonstrated by
  code inspection and unit tests of the identifier-generation function, which
  the project's own documentation explicitly characterizes as "a weaker form
  of evidence than an actual repeated run," and states this distinction rather
  than blurring it.

---

## 6. Validation and Quality-Control Methodology

Validation across Phases 1–2 is structured in four distinct, increasingly
broad tiers, and the project's documentation is careful to keep them
distinguishable:

1. **Structural/schema validation** — does each record/manifest entry conform
   to its defined shape and vocabulary (e.g. `field_status` values drawn only
   from the defined vocabulary)? Established at Phase 1 (`phase1_validation_report.json`)
   and re-checked at every subsequent layer.
2. **Component (single-layer) validation** — is one layer (UMR, temporal
   policy, benchmark organization, reproducibility metadata) internally
   correct on its own terms? Each of Phases 2.2–2.5 implements its own
   component validator.
3. **Cross-layer / substrate validation** — do the independently-validated
   layers actually agree with each other, and does the combined whole satisfy
   invariants no single layer's own validator could express (Phase 2.6, 29
   checks)?
4. **Freeze/acceptance validation** — a final, whole-Phase re-confirmation
   (Phase 2.7), producing one canonical identity as the acceptance artifact.

**Exact recorded numbers, where available**:

| Validation | Result | Source |
|---|---|---|
| Phase 1 (10 checks) | 9 PASS, 1 FAIL (encoding), `overall_status: FAIL` | `phase1_validation_report.json` |
| Phase 2.2 (UMR cross-dataset) | PASS, 1,266,194 records, 0 collisions | `phase2_2_unified_memory_validation_report.json` |
| Phase 2.3 (temporal, 7 checks) | PASS on every check | `phase2_3_temporal_validation_report.json` |
| Phase 2.4 (organization, 12 checks) | PASS, 28/28 resources organized | `phase2_4_benchmark_organization_validation_report.json` |
| Phase 2.5 (reproducibility) | [TO VERIFY — see 3.5] | `data/reports/` (report file not directly confirmed in this pass) |
| Phase 2.6 (substrate, 29 checks) | PASS on every check | `phase2_6_benchmark_substrate_validation_report.json` |
| Phase 2.7 (freeze) | `PASS WITH ISSUES` (honest carry-forward status) | `phase2_freeze_manifest.json` |

Where an exact count could not be directly re-confirmed during this
reconstruction (Phase 2.5's own standalone validator), this is marked
[TO VERIFY] rather than estimated.

---

## 7. Methodological Design Principles

The following principles can legitimately be said to govern Phases 1–2, in
that each is stated explicitly in the project's own documentation and is
enforced by at least one automated check, not asserted only in prose:

- **Provenance preservation.** Every record and every resource carries an
  explicit account of where it came from; nothing is presented as if its
  origin were unknown or irrelevant.
- **Honest representation of absence and uncertainty.** A missing or
  not-yet-computed value is always represented as an explicit `null`/`[]`
  paired with a reason code from a closed vocabulary — never as a fabricated
  default, and never as an empty string standing in for "missing."
- **Separation of raw source data from derived artifacts.** Raw files are
  immutable after acquisition and integrity-checked on an ongoing basis;
  derived output lives in clearly separate directories and is understood to be
  regenerable from raw data plus code, not a second independent source of
  truth.
- **Deterministic, reproducible organization.** Manifest-building functions are
  pure functions of their inputs; determinism is verified by direct tests, not
  assumed.
- **Explicit, enforced resource roles.** A resource's benchmark role is a
  classification of existing data, never a new judgment invented ad hoc, and
  the boundary between roles (especially the memory-foundation boundary) is
  enforced by code, with a synthetic test proving the enforcement actually
  fires.
- **Validation before downstream extension.** Each phase validates its own
  output before the next phase is permitted to build on it, and later phases
  re-validate earlier ones rather than trusting a cached result indefinitely.
- **No silent data manipulation.** Corrections, exclusions, and quarantines are
  always logged with a reason and preserved (not deleted), and reprocessing a
  dataset without a version bump and a new completion record is explicitly
  named as a boundary violation.
- **Traceability of derived artifacts.** Every version number in every
  downstream manifest is read from a single upstream source-of-truth constant,
  never independently re-declared, so that version drift between documents
  describing the same fact is structurally prevented rather than merely
  discouraged.

---

## 8. Phase 1–2 Outputs

| Phase | Methodological Activity | Primary Output | Validation |
|---|---|---|---|
| 1 | Resource identification, registration, acquisition, cleaning, quality classification | `resource_registry.json`; `data/processed/<dataset>/*.jsonl` for 4 core datasets | 10-check validation, 9 PASS / 1 FAIL (`phase1_validation_report.json`) |
| 2.1 | Data-boundary definition; Phase 2 input approval | `phase2_input_manifest.json` | Boundary/immutability tests (`test_phase2_boundary.py`) |
| 2.2 | Unified schema mapping (Unified Memory Record) | `data/processed/unified_memory/<dataset>/memory_records.jsonl` (schema 1.1.0) | Cross-dataset validator, PASS, 1,266,194 records |
| 2.3 | Temporal normalization | Additive UMR fields (`normalized_timestamp`, `temporal_provenance`, `benchmark_timestamp`) | 7-check validator, PASS |
| 2.4 | Benchmark-role organization | `benchmark_resources.json` | 12-check validator, PASS, 28/28 organized |
| 2.5 | Reproducibility identity | `reproducibility_manifest.json` | [TO VERIFY] |
| 2.6 | Cross-layer substrate validation | `phase2_6_benchmark_substrate_validation_report.json` | 29-check validator, PASS |
| 2.7 | Acceptance and freeze | `phase2_freeze_manifest.json` | Whole-Phase canonical identity hash, status `PASS WITH ISSUES` |

---

## 9. Scope Boundary

**Phases 1–2 do not establish, and this document does not describe:**

- the clean agent-memory execution environment (agent architecture, memory
  retrieval/selection/use, evaluation harness) — a Phase 3 activity;
- any memory lifecycle, versioning, supersession, or provenance-graph
  construction over the memory substrate — Phase 3;
- memory-poisoning attack implementation, reconstruction, or execution of any
  kind (AgentPoison, MINJA, DSRM, MemoryGraft, FARMA, MPBench, or any other) —
  Phase 4;
- sleeper/dormant-poisoning dataset generation or activation — later phases;
- any defense, mitigation, containment, or attack-origin attribution mechanism
  — later phases;
- any GNN/GLN training or analysis — later phases;
- agent execution or experiment orchestration of any kind.

The project's own Phase 2.6/2.7 validation explicitly includes a structural
scan confirming that no function or class definition implementing any of the
above exists anywhere in the Phase 1–2 codebase (`preprocessing/`) — this is
not merely a scope statement in prose, but a checked invariant. Attack, sleeper,
and evaluation resources are identified, registered, and organized by role in
Phases 1–2, but their **experimental activation** — actually being run, used to
generate poisoned data, or evaluated against — occurs, if at all, only in later
phases (Phase 4 for attacks; Phase 3 for workload resources), a distinction the
project's documentation calls the "experimental activation boundary" and states
explicitly for each resource category.

---

## 10. Known Limitations / Items for Professor Review

- [TO VERIFY] The exact validation-check count and PASS/FAIL result for Phase
  2.5's own standalone reproducibility validator was not directly located as
  an independent report during this reconstruction; only its re-invocation
  inside Phase 2.6's cross-layer check was confirmed. Should be confirmed
  against the repository directly before this draft is finalized.
- [TO VERIFY] The registry module's own code comment states "27 resources"
  while the generated data and entry count agree at 28 — recorded in the
  project's own issue log as a stale comment, not a data inconsistency, but
  worth an explicit correction pass.
- [PROFESSOR REVIEW] No single narrative document in the repository explains
  the original literature-review-level justification for selecting these four
  specific memory datasets (as opposed to other candidates) as the project's
  memory foundation — only each dataset's individual `research_purpose` is
  recorded. If a higher-level justification exists in `Methodology.pdf` or the
  project's literature-review materials, it was not consulted for this draft
  and should be incorporated or cited explicitly.
- [PROFESSOR REVIEW] Several source datasets' version/revision information is
  genuinely `"unavailable"` because the upstream publisher never issued a
  version tag (LoCoMo, LongMemEval, Conversation Chronicles) — this is a
  property of the source data, not a project gap, but is worth flagging
  explicitly for a methodology section, since a reader might otherwise assume
  an oversight.
- [PROFESSOR REVIEW] No dependency lockfile or automatic code-state stamping
  exists (Section 5) — a genuine, currently-open reproducibility gap the
  project's own documentation records as intentionally out of scope for
  Phases 1–2 specifically, deferred to later phases or general project
  hygiene.
- [PROFESSOR REVIEW] Phase 1's own documentation is comparatively thin
  compared to Phase 2's (which has a full `docs/phase2/` narrative
  documentation set); Phase 1's methodology in this draft was reconstructed
  primarily from code and JSON reports rather than from a Phase-1-equivalent
  narrative document, because none currently exists in the repository. Worth
  noting explicitly to the professor as a documentation-completeness gap, not
  a methodological one.

---

## SOURCE TRACEABILITY CHECK
*(Internal verification section — for review purposes; may be removed from the
professor-facing version.)*

| Section | Primary evidence used | Directly documented vs. reconstructed | Uncertainty |
|---|---|---|---|
| 1. Overview | `docs/phase2/DATA_BOUNDARY.md`, `docs/phase2/PHASE2_FREEZE.md` | Directly documented (the layering principle is stated verbatim in the repository) | Low |
| 2.1 Dataset identification | `preprocessing/registry.py` (full module read), `data/metadata/resource_registry.json` | Directly documented (registry is the primary source) | Low, except the "why these four" higher-level justification (flagged) |
| 2.2 Registry mechanics | `preprocessing/registry.py`, `docs/phase2/DATA_VERSIONING_POLICY.md` | Directly documented | Low |
| 2.3 Categorization | `preprocessing/registry.py`, `docs/phase2/BENCHMARK_ORGANIZATION.md` | Directly documented | Low |
| 2.4 Provenance/integrity | `docs/phase2/DATA_BOUNDARY.md`, `docs/phase2/DATA_VERSIONING_POLICY.md` | Directly documented | Low |
| 2.5 Phase 1 validation | `data/reports/phase1_validation_report.json` (read directly) | Directly documented (raw JSON report) | Low |
| 2.6 Phase 1 limitations | `docs/phase2/ISSUES_REPORT.md` (read in full) | Directly documented | Low |
| 3.1 Phase 2.1 | `docs/phase2/DATA_BOUNDARY.md` (read in full) | Directly documented | Low |
| 3.2 Phase 2.2 | `docs/phase2/UNIFIED_MEMORY_RECORD.md` (read in full) | Directly documented | Low |
| 3.3 Phase 2.3 | `docs/phase2/TEMPORAL_NORMALIZATION.md` (read in full) | Directly documented | Low |
| 3.4 Phase 2.4 | `docs/phase2/BENCHMARK_ORGANIZATION.md` (read in full) | Directly documented | Low |
| 3.5 Phase 2.5 | `docs/phase2/BENCHMARK_METADATA_AND_MANIFESTS.md` (partial read, first ~80 lines) | Partially reconstructed — the specific validator-check enumeration for Phase 2.5 alone was not located | Medium — flagged [TO VERIFY] |
| 3.6 Phase 2.6 | `docs/phase2/BENCHMARK_SUBSTRATE_VALIDATION.md` (read in full) | Directly documented | Low |
| 3.7 Phase 2.7 | `docs/phase2/PHASE2_FREEZE.md` (read in full) | Directly documented | Low |
| 4. Mapping | Synthesized from 3.1–3.7's own already-verified sources | Reconstructed synthesis, not a single-document copy | Low (structure matches the project's own documented chain) |
| 5. Reproducibility | `docs/phase2/REPRODUCIBILITY_REPORT.md` (read in full), `docs/phase2/DATA_VERSIONING_POLICY.md` | Directly documented | Low |
| 6. Validation numbers | Direct reads of `data/reports/phase1_validation_report.json` and the phase2_2/2_3/2_4/2_6 validation reports/docs | Directly documented, except Phase 2.5's own standalone count | Medium for Phase 2.5 row only |
| 7. Design principles | Synthesized across all of the above | Reconstructed synthesis | Low |
| 8. Outputs table | Synthesized across all of the above | Reconstructed synthesis | Low |
| 9. Scope boundary | `docs/phase2/PHASE2_FREEZE.md` §16–18, `docs/phase2/BENCHMARK_SUBSTRATE_VALIDATION.md` §15 | Directly documented | Low |
| 10. Limitations | Synthesized from all [TO VERIFY]/gap notes surfaced above | Reconstructed synthesis | N/A (this section exists to record uncertainty) |

**Not consulted for this draft** (explicitly out of scope for this
reconstruction pass, flagged for the professor's awareness): `Methodology.pdf`,
`PROCESS DOCUMENTATION.docx`, `MAMBench Process Documentation.docx`, and the
project's literature-review draft — all present in the repository root but not
read during this pass, since the instructions specified reconstruction from
"the ACTUAL repository, Phase 1–2 reports, implementation, experiment records,
manifests, dataset organization, validation artifacts, and documented
decisions," and these root-level documents were treated as a secondary,
narrative source rather than the primary evidentiary basis. If the professor
wants this draft cross-checked against those documents specifically, that is a
reasonable, distinct follow-up pass.
