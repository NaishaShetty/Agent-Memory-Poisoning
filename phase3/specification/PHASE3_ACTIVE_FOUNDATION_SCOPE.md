# Active Memory Foundation Scope

Status: **DECISION, NOT FROZEN** — records a real scope decision made explicitly by the
user during this session's Phase 3 completion audit, closing a documentation gap the
audit itself flagged (checklist §14/§27: no document stated this decision).

## 1. The decision

**Mem0 and A-MEM are the only active, primary memory foundations for MAMBench.**

This narrows the original strengthening plan's own framing
([MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md](MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md),
written earlier in this session), which listed Mem0, A-MEM, and Graphiti as primary
foundations, with only Letta as secondary/deferred. That framing is superseded by this
document for scope purposes; the strengthening plan's own technical content (Initiatives
A–G) remains valid and applies to Mem0/A-MEM exactly as built and verified.

## 2. Why (as established during this session, not merely asserted)

- **Mem0**: real, `QUALIFIED` (Initiative D, 15/15 fixtures), real counterfactual
  measurement complete (Initiative A, n=6 LoCoMo tasks), fully local (no server, no API
  key), live-wired into the real campaign path (Condition B).
- **A-MEM**: real, `QUALIFIED` (15/15 fixtures), real counterfactual measurement complete
  (post-`inspect_memory()`-fix, n=6, directly comparable to Mem0's own result), fully
  local (in-memory ChromaDB, no server, no API key), live-wired into the real campaign
  path (Condition C).
- **Graphiti**: confirmed, this session, to have no local embedder at all —
  `graphiti-core` supports only OpenAI/Azure/Gemini/Voyage cloud APIs. Qualifying it would
  require a real cloud API key (e.g. Gemini's free tier) and a graph database backend
  (Neo4j/FalkorDB), neither of which this project has stood up. This is a real
  infrastructure/policy cost, not a technical blocker in the same sense Mem0/A-MEM's
  gaps were — and the user's own judgment, made explicitly during this audit, is that it
  is not worth incurring for the current project scope.
- **Letta**: requires a self-hosted server (the full `letta` package, explicitly
  documented as "heavy... explicitly out of scope" in the real adapter's own code
  comments) or a Letta Cloud account — a bigger lift than Graphiti's, and was marked
  secondary/deferred from the very first version of the strengthening plan, never
  revisited.

## 3. What this means going forward

- No further qualification, wiring, or counterfactual-measurement work is expected for
  Graphiti or Letta under the current project scope.
- No Gemini/API-key integration, and no Neo4j/FalkorDB/Ollama/Letta-server infrastructure,
  is required to consider the memory foundation "ready" for its intended purpose.
- The objective is depth, qualification, observability, and scientific defensibility for
  two foundations exercised for real — not maximizing the number of memory frameworks
  covered.
- If this scope is revisited later (e.g. a future stage decides Graphiti is worth the
  cloud-API cost), that is a new decision requiring its own explicit sign-off — this
  document does not pre-authorize it, and reversing it should update this file rather than
  leave two contradictory scope statements in the repository.

## 4. Freeze status

Not a frozen decision in the same sense as the strengthening plan's technical content —
this is a project-scope decision, recorded here so it is written down rather than living
only in conversation. Supersedes the foundation-scope framing (not the technical content)
of `MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md`.
