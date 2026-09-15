# Phase 6 Defense Literature & Existing-System Audit

Status: 6.2 deliverable. Findings below come from direct investigation of primary
sources (papers and, where public, actual repository code) — not from the Phase 1
registry's own summaries, which recorded acquisition metadata only (every one of
these resources has `local_path: null` in `data/metadata/resource_registry.json`;
none had been read at the mechanism level before this audit). Where a claim could not
be independently verified (one paywalled paper), that is stated explicitly rather than
inferred from an abstract.

Two research tracks were run: (A) the eight security-benchmark/defense resources
already registered in Phase 1, and (B) the seven Phase 4 attack papers' own
defense/mitigation sections, since several turned out to contain real, quantified
defense evaluations MAMBench had never examined (only their attack mechanisms were
ported in Phase 4).

---

## Track A — Registered Security-Benchmark/Defense Resources

### A.1 MemSecBench (arXiv:2607.27080)
**Not a defense.** A "Write→Execute→Forget" measurement protocol across 24
agent/memory/LLM configurations, quantifying how often poisoned content persists
(84.2% of cases) and drives a full malicious write→execute chain (50.3%). Its
"selective repair" component is a two-stage regex+LLM-judge intercept used to *test*
repair effectiveness within the harness, not a standalone defense algorithm. No repo.
Relevance to Phase 6: a candidate *evaluation methodology* (persistence/consequence
tracking) MAMBench could optionally apply to its own attacks, but contributes no
mechanism.

### A.2 MEMSAD (arXiv:2605.03482)
Real detection-only defense: rolling query-history cosine-similarity anomaly scoring
against a calibrated benign threshold (`μ̂ + κσ̂`), grounded in a proven
gradient-coupling theorem (anomaly-score gradient = retrieval-objective gradient for
*continuous* embedding perturbations). Cheap (~2ms/entry), no LLM, retrieval-stage.
TPR=1.00 on AgentPoison but only 0.20–0.40 on MINJA/InjecMEM. **Critical, author-proven
limitation**: the theorem's guarantee explicitly does not cover discrete token/synonym
substitution — a formally demonstrated blind spot (80–100% evasion with 3–5
substitutions/entry). This is precisely the attack style MAMBench already runs
(MPBench-PCFI's "unmarked, plausible... ordinary domain knowledge," FARMA's
natural-language forged reasoning traces) — MEMSAD's own theory predicts it will
underperform against exactly the attacks MAMBench most needs defended. No repo;
untested on conversational-memory (LoCoMo-style) domains.

### A.3 MemAudit (arXiv:2605.23723)
Real defense, but **post-hoc forensic**, not real-time: a Counterfactual Memory
Influence Score (ablate-and-replay against an observed harmful outcome) plus a
Memory Consistency Graph (NLI-based contradiction detection). Needs labeled harmful
outcomes to compute its core score, and is LLM-call-heavy (full re-retrieval +
re-generation per ablation) — impractical to run continuously over a 20-candidate
pool per query. Evaluated only against MINJA. This is the resource the registry
itself flagged as conceptually closer to a **Phase 7 forensic/attribution** tool than
a Phase 6 real-time defense — confirmed by direct mechanism inspection, not merely
inherited from the registry's note.

### A.4 MPBench's own defense proposal (arXiv:2606.04329)
Confirmed: **no implemented or evaluated defense exists in this paper.** Section 5
offers three prose-level recommendations (tighter write policies, architectural
hardening via source isolation/provenance/compaction filters, post-write monitoring
against "authorized behaviors") with no algorithm, no metrics, and no baseline
comparison. The paper does report a real negative result: existing prompt-injection
defenses tested against MPBench's own taxonomy fail on "weak-signal" attacks with no
syntactic anomaly — directly relevant, since MPBench-PCFI (already in Phase 4) is
exactly this weak-signal class. Nothing here is adoptable as a mechanism.

### A.5 A-MemGuard (arXiv:2510.02373, ICML 2026 poster)
**Real, live repo** (github.com/TangciuYueng/AMemGuard), the strongest external
candidate found. Two coupled, label-free mechanisms: (1) consensus-based validation —
converts each retrieved candidate into a structured entity-relation reasoning path,
then an LLM-as-judge checks cross-candidate consistency and flags divergent paths as
anomalous; (2) a dual-memory "lessons" store — flagged reasoning patterns are recorded
verbatim, and before the agent commits to a plan, its own proposed plan is checked
against this lessons store and prefixed with an explicit warning on a match.
Intervenes **after retrieval, before use** — it does not gate admission, and poisoned
content persists in the main store indefinitely; the defense instead reduces the
poison's *effect* every time it is retrieved, and accumulates institutional memory
against repeat exploitation. Evaluated against AgentPoison, MINJA, and multi-agent
misinformation — not against FARMA, MemoryGraft, DSRM, MPBench-PCFI, or Sleeper.
Cost: ~2x token overhead (reported 7.8K vs 3.6K undefended, EHRAgent). No explicit FPR
number — only an indirect benign-accuracy proxy. **Known structural weakness**:
because the mechanism rewards cross-candidate *agreement*, a coordinated attacker who
injects several mutually-consistent poisoned memories (this is architecturally close
to what FARMA's amplification and MemoryGraft's precedent-building already do) could
produce a consensus that is itself malicious — the LLM-judge sees agreement, not
ground truth. This is a real, disclosed limitation, not a hypothetical one, and it is
concerning specifically because two of MAMBench's seven attacks (FARMA, MemoryGraft)
are designed around exactly this kind of manufactured-consensus mechanism.

### A.6 ASB — Agent Security Bench (arXiv:2410.02644, ICLR 2025)
Live repo; broad benchmark, only a small slice (1 of ~28 attack/defense combinations)
targets memory poisoning specifically. Its two memory defenses — perplexity filtering
and LLM-based judgment — are a **documented negative result by the paper's own
authors**: FNR≈0.66, FPR≈0.20 against ASB's (comparatively simple) memory-poisoning
attack. Perplexity filtering is trivially evaded by fluent natural-language poison,
which is exactly what all seven of MAMBench's attacks produce (none inject gibberish
adversarial tokens into memory *content* — even AgentPoison's optimized tokens are a
retrieval trigger, not the poisoned content payload itself). Useful as an explicitly
weak comparison baseline, not as a candidate mechanism.

### A.7 AgentDojo (arXiv:2406.13352, NeurIPS 2024) — poor fit, confirmed
Not a memory-poisoning system. Single-episode tool-output prompt injection; no
persistent, cross-session memory store exists in its threat model at all. Its one
defense (a tool-call filter) operates entirely outside any lifecycle stage MAMBench
defends. Excluded from serious candidacy — included in the registry only as an
adjacent benchmark-design reference, per its own Phase 1 entry.

### A.8 InjecAgent (arXiv:2403.02691, ACL Findings 2024) — poor fit, confirmed
Attack-only benchmark; no defense mechanism exists anywhere in the repository or
paper to evaluate. Same conclusion as AgentDojo: not memory-lifecycle related,
excluded from candidacy.

---

## Track B — The Seven Attack Papers' Own Defense Sections

This track surfaced a real documentation discrepancy in this project's own frozen
record, disclosed per Rule 20 rather than silently corrected: **the Methodology
Draft and PHASE4 dossiers describe a combined "FARMA/DSRM" attack lineage as if the
two names trace to related work; they do not.** DSRM (Jing, Li, Dong, Zhou, Liu,
*Engineering Applications of AI* vol 167, 2026) and FARMA (Karamchandani,
Nagasubramaniam, Zhu, Wu, arXiv:2607.05029) are two entirely distinct papers, by two
distinct author teams, with two mechanistically unrelated attacks (DSRM = two-stage
self-refine + InfoNCE-style semantic-reasoning deception; FARMA = forged-reasoning
seed + amplification via manufactured precedent counts). MAMBench's own Phase 4
implementation already treats them as separate attacks with separate code — this is
purely a citation/lineage-description artifact in the prose documentation, not a
functional defect, and it is **not corrected here** (correcting frozen Phase 4
documentation is out of this audit's scope) — it is flagged for whoever next revises
that documentation.

### B.1 AgentPoison's own defense (Appendix A.2.4)
Tests perplexity filtering and query rephrasing. Both largely fail: ASR-t remains
47.2–62.0% under either defense (vs. much larger drops for less-fluent baseline
attacks like GCG). AgentPoison's optimized triggers are fluent enough to evade
input-sanitization defenses built for less natural adversarial text.

### B.2 MINJA's own defense (Section 5.4, "Potential Defense")
A real, evaluated section — and a real negative result. Adversarial training:
dismissed as impractical, not run. Embedding-space sanitization: tested, **failed**
(malicious/benign records are "highly entangled," not separable). Prompt-level
detection: works only narrowly — a domain-targeted prompt catches 131/135 on its own
domain but 0/135 elsewhere; a general prompt catches roughly half with heavy false
positives (34/50 on an unrelated domain). System-level access controls: discussed,
not empirically tested, noted as circumventable. MINJA's own authors conclude there is
no winning defense among what they tried — this paper's own attack surface (query-only,
agent-mediated insertion via ordinary conversational turns) is genuinely hard to
distinguish from benign content at admission time, a finding directly relevant to
Phase 6's D1 design.

### B.3 DSRM's own defense — **UNRESOLVED, partial evidence only**
The DSRM paper (*Engineering Applications of AI*, DOI 10.1016/j.engappai.2026.113968)
is paywalled; full text was not accessible (403 on all attempted routes, including a
scilit mirror). No defense/mitigation section could be found in any available
abstract, snippet, or third-party summary. **This audit does not claim DSRM's paper
lacks a defense section — it reports that none could be found with available access,
and flags this as an open item** requiring direct institutional access before it can
be ruled in or out as a candidate.

### B.4 FARMA's own defense — SENTINEL (arXiv:2607.05029, Section on defenses)
**The single strongest, most rigorously evaluated defense found across both research
tracks.** A 5-layer write-time (admission) pipeline: keyword filter → provenance/IFC
taint labeling → taint-threshold filtering → pattern/risk screening → **Reasoning
Guard**, a weighted heuristic scorer (5 equally-weighted signals: provenance anomaly,
self-reference/precedent-count mismatch, suspicious decision-log vocabulary density,
implausible-perfection claims, structural-template anomaly; reject if weighted sum
exceeds τ=0.5). Reported results: FARMA ASR reduced to 0% (EHR, RAP domains, from
100%/48% baseline) and 6% (ReAct-QA, from 52% baseline), across three different LLM
backbones, with **0% false-positive rate across 326 benign traces**. Ablation
confirms the Reasoning Guard layer alone is necessary and sufficient — removing it
restores 100% ASR. It is heuristic/regex-based, requires no attack-specific labels
or training data, and reports <1ms per-write overhead. **Author-disclosed
limitation**: explicitly vulnerable to an adaptive attacker who knows SENTINEL's exact
heuristics; a preliminary paraphrase-adaptive variant showed only limited protection,
left as the paper's own future work. Mechanistically, SENTINEL's signal set (fake
self-reference counts, "established pattern"/"pre-validated" vocabulary, perfection
claims, template anomalies) targets *reasoning-trace-style* forged memories
specifically — this generalizes plausibly to MemoryGraft (forged "successful
experience" records) and Sleeper (fabricated dormant records), but has no obvious
purchase against AgentPoison/DSRM's optimized-trigger-token attacks (which target
retrieval ranking, not reasoning-trace content) or MPBench-PCFI (deliberately
designed to look like ordinary factual content with none of SENTINEL's five target
signals). This is a genuine, checkable generalization gap, not a hypothetical one.

### B.5 MemoryGraft's own defense (Section 6, "Potential Defense") — untested by its own authors
Two proposals, neither empirically evaluated in the paper: Cryptographic Provenance
Attestation (signed writes via a trusted execution environment — architecturally
heavy, requires key infrastructure MAMBench does not have and should not build for
this reason alone) and Constitutional Consistency Reranking (score retrieved traces
against a "safety constitution" penalizing phrases like "bypassing validation";
filter above a risk threshold at retrieval time — lightweight, general, but the
source paper gives no quantified results at all). If MAMBench prototypes this
reranking idea, it must be labeled a **novel implementation MAMBench validates
itself**, never described as "reproducing MemoryGraft's own tested defense" — the
paper never tested it.

### B.6 Sleeper Memory Poisoning's own defense (Section 6.3 + Appendix J)
Real, evaluated, but explicitly uneven. Prevention: prompt hardening (naive and
GEPA-optimized) and "extreme spotlighting" (explicit untrusted-content tagging).
Detection: an LLM document scanner pre-screening ingested documents (localization
score >0.96 on one backbone). Authors' own honest conclusion: brittle against adaptive
attackers — GEPA-hardening, tuned against one adaptive variant, *raised* the
injection rate from 6.2% to 64.6% on a different model (Kimi-K2.6) under a different
adaptive attack. This is a directly relevant, sobering data point for Phase 6's own
Stage 6.14 (adaptive/evasive evaluation): a defense tuned against one adaptive
attacker can become worse than no defense against a different one. The document
scanner is the more promising piece for Stage 6.8 (Sleeper-specific defense), feasible
to reimplement as a pre-ingestion LLM-scan step, reported with the same "uneven,
model-dependent" caveat.

---

## Cross-Cutting Observations

1. **No single external defense — from either track — spans more than one or two of
   the four lifecycle layers (D1–D4) Phase 6's charter defines.** SENTINEL is
   admission-only (D1). A-MemGuard is retrieval/use-time plus a novel containment
   mechanism (D3, arguably touching D4). MEMSAD is retrieval-only (D3) and provably
   weak against paraphrase attacks. MemAudit is post-hoc, outside the real-time
   lifecycle entirely. None addresses D2 (a persistent trust/provenance state
   propagating across storage and derivation) as a first-class mechanism at all —
   this is a genuine, structural gap across the entire literature reviewed, not a
   MAMBench-specific oversight.
2. **No external defense has been evaluated against more than 2–3 attack mechanisms
   at once**, and none has been evaluated against anything resembling MAMBench's
   full seven-attack, cross-family spread (gradient-optimization, query-only,
   forged-reasoning, gated-experience, self-refinement, weak-signal-fact,
   dormant-trigger). Every defense's own reported generalization is narrower than
   what Phase 6's RQ requires.
3. **Multiple defenses (AgentPoison's, MINJA's, ASB's) are documented negative
   results by their own authors.** These are scientifically valuable as known-weak
   comparison baselines, not as candidates to adopt.
4. **The strongest two candidates (A-MemGuard, SENTINEL) are each faithfully
   reproducible** — real algorithms, precisely specified, no dependency on
   unavailable infrastructure — but faithful reproducibility is necessary, not
   sufficient, for adoption as *the* Phase 6 defense, per the scope requirement that
   the RQ is about lifecycle-spanning intervention.
