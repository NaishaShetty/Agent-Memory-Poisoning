# Licensing and Data Rights (status as of 2026-10-12)

**Decision status:** no licence has been applied. The owner deferred this decision on purpose (Results §11 (vii)). This document records the constraints that decision must respect. **It does not choose a licence.** Register item REP-1.

## 1. Upstream sources and the licences recorded for them

"Where recorded" means where in this repository the licence is written down. No licence was verified against the upstream site during the remediation; every entry should be confirmed there before release.

| Source | Used for | Licence | Where recorded |
|---|---|---|---|
| LoCoMo (snap-research) | Owner conversations, benign memories, corroboration evidence, every memory store | **CC BY-NC 4.0** | `data/metadata/dataset_manifest.json`; Methodology §16 |
| LongMemEval (cleaned) | Phase 3 tasks; Phase 14 | MIT (HF dataset card) | `dataset_manifest.json` |
| Conversation Chronicles | Phase 1–2 substrate | CC BY 4.0 (HF dataset card) | `dataset_manifest.json` |
| Multi-Session Chat (MSC) | Phase 1–2 substrate | **No explicit dataset licence published**; ParlAI code is MIT | `dataset_manifest.json` |
| Gandalf (`Lakera/gandalf_ignore_instructions`) | Hold-out 1 | MIT | `external_test_corpus.py` |
| deepset prompt injections | Hold-out 1 | CC BY 4.0 | `external_test_corpus.py` |
| Mosscap (`Lakera/mosscap_prompt_injection`) | Hold-out 2 | MIT | `holdout2_corpus.py` |
| in-the-wild jailbreak prompts (`TrustAIRLab`) | Hold-out 3 | MIT | `holdout3_corpus.py` |
| toxic-chat | Hold-out 5 | **CC BY-NC 4.0** | `holdout5_corpus.py` |
| SPML Chatbot Prompt Injection | Hold-out 6 | MIT | `holdout6_corpus.py` |
| MINJA, AgentPoison, BIPIA, AgentDojo | External development set | MIT | `external_attacks.py` |
| InjecAgent | External development set | **Not recorded in this repository**; verify upstream | — |
| LLM-authored corpora (qwen2.5, mistral, gemini-3.5-flash-lite) | Own attacks; hold-outs 4, 7, 8; SA-1 | Governed by each model's licence and terms of use. Not reviewed during the remediation. | — |

## 2. Consequences

1. **Derived data inherits non-commercial terms.** Any released file containing LoCoMo text or toxic-chat text carries CC BY-NC 4.0 obligations: non-commercial use and attribution. That covers the stores, owner turns, hold-outs 4, 7 and 8, the benign notes written "about" LoCoMo owners, SA-1, and hold-out 5.
   - A permissive licence on the whole repository would be incompatible with those files.
2. **MSC has no stated dataset licence.** Do not redistribute MSC-derived records. Release the scripts that rebuild them from the upstream source instead.
3. **Code and data can be licensed separately.** The code in this repository is the project's own work, so a permissive code licence (e.g. MIT or Apache-2.0) is possible, with data files carved out. This is the usual pattern, but choosing it is the owner's decision.
4. **LLM-generated text.** Check each provider's output terms before redistributing generated corpora. This remediation did not perform that review.

## 3. Minimal releasable package, if the owner chooses to release

| Component | Contents | Constraint |
|---|---|---|
| Code | `phase17/`, `phase6/`, and the phases they import; the test suite; `phase17/remediation/` | Owner's choice of code licence |
| Frozen manifests | SHA-256 digests and freeze records for hold-outs 1–8 and SA-1 | Shareable: hashes only |
| Per-item decisions and judge verdicts | `phase17/data/*.json` | Contain source text. Release under the most restrictive upstream licence of the text they contain, or strip the text and keep ids + decisions |
| Rebuild scripts | `*_corpus.py` builders | Shareable. Users fetch upstream data themselves |

Until a licence is chosen, the paper should say: "code and evaluation artifacts available from the authors on request; licensing of derived data is constrained by CC BY-NC 4.0 sources." That wording does not claim a public release that does not exist.
