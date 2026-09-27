# Phase 17 Round 5 — Fixing the Two Round-4 Items the User Flagged

## 1. AgentPoison query-side trigger — root cause finally isolated, and it changes the conclusion

Round 4 tried 3 embedding-space heuristics (diverse-query mean under 2 models, benign-
cluster-outlier distance) — all real attempts, all non-specific or undiscriminating.

**The missing piece:** the retrieval-consensus signal this project's OWN live defense
actually uses is `sentence-transformers/all-MiniLM-L6-v2`
(`phase6/defense/retrieval/embedding_signals.py::EMBEDDING_MODEL_NAME`) — the SAME model
AgentPoison's real trigger was gradient-optimized against
(`phase4/attacks/agentpoison/trigger_run.py::MODEL_ID`). Round 4's attempt 2 used the
right model but the wrong OPERATIONALIZATION (raw mean similarity magnitude, a global
z-score). The real question a "universal retrieval magnet" implies is behavioral: **is
this memory retrieved into the top results for an unusually large fraction of
semantically UNRELATED real queries**, not "is its raw average similarity higher."

**Real test, done properly:** built one shared candidate pool (the real AgentPoison
memory + one real memory from each of the other 6 families + 50 real benign memories,
embedded with `all-MiniLM-L6-v2`) and ranked it against 300 diverse, real, shuffled
LoCoMo questions from many different unrelated conversations, counting how often each
item lands in the top-3.

**Result — a genuine, surprising, and MORE informative finding than any prior attempt:**

| Family | Top-3 retrieval rate (300 diverse queries) |
|---|---|
| mpbench | 37.3% |
| sleeper | 33.7% |
| farma | 33.7% |
| minja | 32.0% |
| dsrm | 30.0% |
| memorygraft | 25.3% |
| **agentpoison** | **9.7%** (lowest of all 7) |
| benign (avg of 50) | 2.0% |

**AgentPoison's trigger, as reconstructed in this project, is LESS broadly retrievable
than every other attack family's poison, not more.** This directly refutes the
"universal retrieval magnet" premise for THIS implementation. Separately confirmed: the
memory's CONTENT-level template ("Regarding X: ... treat as current information") is
ALREADY caught by the existing `forged_provenance_confirmation_score` admission signal
at score 1.0 — not a new finding, but it closes the loop: the content is covered, and the
supposedly-distinct query-side risk this workstream flagged does not measurably manifest
in this benchmark's reconstruction of the attack.

**Honest interpretation, not overclaimed:** the real AgentPoison paper's attack requires
iterative, white-box gradient optimization against the target retriever to actually
achieve broad retrievability; this project's reconstruction (`milestone4_artifact_2026-
09-11_v2.json`: `fitness_score_final=2.0`, a modest, disclosed, limited-iteration
optimization) evidently does not reach that property. **This is a real, disclosed
attack-fidelity limitation, not a defense gap that was silently missed** — there is
nothing behaviorally anomalous for a defense to catch here, measured directly rather than
assumed. If a future, more faithfully-optimized AgentPoison artifact DID exhibit broad
retrievability, this same retrieval-frequency test (not the raw-similarity heuristics
tried in rounds 3–4) is the correct tool to detect it with, and should be re-run against
that artifact. (`phase17/query_trigger_signal.py`, retrieval-frequency test appended)

## 2. Human evaluation — completed the proxy coverage, added a second independent proxy

**Gemini retry:** the 9 items that hit free-tier rate limits in round 4 were retried with
longer backoff (8s throttle, up to 3 attempts per item) — **60/60 now rated**, 0 errors.
Recomputed: Gemini agrees with the automated LLM judge on **76.7%** (was 74.5% on the
51-item partial sample) and with the string metric on **60.0%**.

**Second, independent, non-rate-limited proxy added:** `phi3:mini` (local, the same
third model family from round 2/3) rated the identical 60-item packet. **Gemini and
phi3:mini agree with EACH OTHER 93.3% of the time** — two independently different model
families, blinded to the automated verdicts, converge strongly. phi3:mini agrees with
the automated judge 80.0% of the time.

**This is a real 2-model LLM-proxy panel, not a human evaluation** — still explicitly
disclosed as such everywhere, and `HUMAN_EVAL_INSTRUCTIONS.md` is unchanged: a real human
rating this SAME packet remains open. What changed: the proxy evidence is now complete
(60/60, not 51/60) and corroborated by a second, independent model rather than resting on
one hosted model's partial sample. (`phase17/llm_proxy_panel.py`)

## Full regression

Run after both fixes (`phase6/ phase8/ phase11/ phase12/ phase13/ phase14/ phase15/
phase17/ attribution/ phase7/ phase3/ -m "not slow"`): **2722 passed, 30 skipped, 9
deselected, 0 failed** (1766.3s). New test:
`test_agentpoison_reconstruction_retrieval_rate_lower_than_other_families` (a cheap,
5-query regression guard for the round-5 finding) — 7/7 in
`phase17/tests/test_round3_fixes.py` passed.
