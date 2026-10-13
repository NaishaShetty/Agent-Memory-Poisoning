# Data, Licensing and Annotation Audit

> **Correction (targeted phase, 2026-10-13).** The claim that B13's corroboration thresholds "move about 3x with the calibration owners" is **withdrawn**. It compared the nominal 2%/5% budget at `SUPPORT_TOP_K=20` against shipped constants that sit at a 0.49%/2.05% budget at top-20 (they were calibrated at top_k=5). Leave-one-owner-out calibration over all 10 owners at the shipped budget reproduces B13 (detection 116/200, benign exclusion 15/2,541; thresholds vary 1.15x). See `B13_OWNER_GENERALISATION_REPORT.md`. Annotator 2 was the owner's friend, who labelled on the owner's laptop (owner's clarification); see `ANNOTATION_PROVENANCE_FINAL.md`. No new annotation study is recommended by default.


**Date:** 2026-10-13. **Deliverable 6.**

Every entry below was inspected on 2026-10-13. "Recorded in" says where the information came from:

| Source | Meaning |
|---|---|
| package metadata | `importlib.metadata` in the environment that runs the code |
| `ollama show --license` | The licence text shipped with each local model |
| code | The licence string the corpus builder writes |
| `dataset_manifest.json` | The project's Phase 1 registry |

Nothing here was verified on upstream websites during this audit. **Confirm each upstream licence before any release.** No licence has been applied to the repository: this remains the owner's decision.

---

## 1. Inventory and release treatment

### 1.1 Original MAMBench work

| Component | Upstream / owner | Licence / terms | Redistribute? | Modify? | Attribution | Non-commercial? | Proposed treatment |
|---|---|---|---|---|---|---|---|
| Source code, scripts, configuration (`phase*/`, `phase17/`, `scripts/`) | Project authors | **None applied yet** | Owner decides | Owner decides | — | No | A permissive code licence is possible (no third-party code is vendored into these files); owner decision |
| Documentation, pre-registrations, reports | Project authors | None applied | Owner decides | — | — | No | Same licence as the code, or CC BY 4.0 |
| Frozen-corpus manifests (SHA-256 digests) | Project authors | None | Yes | — | — | No | Release; hashes contain no third-party text |
| Per-item decisions, judge verdicts, caches (`phase17/data/*.json`) | Project authors, **containing third-party text** | Inherit the strictest licence of the text they contain | Partly (see §2) | — | Per source | **Yes, where they contain LoCoMo or toxic-chat text** | Release under CC BY-NC 4.0, or strip the text and release ids plus decisions |

### 1.2 Third-party datasets used for evaluation

| Component | Upstream / owner | Licence / terms | Redistribute? | Modify? | Attribution | Non-commercial? | Proposed treatment |
|---|---|---|---|---|---|---|---|
| **LoCoMo** (owner conversations, benign memories, corroboration evidence, every memory store) | snap-research (Maharana et al., ACL 2024) | **CC BY-NC 4.0** (`dataset_manifest.json`, from the repository's LICENSE.txt) | Yes, NC only | Yes | Yes | **Yes** | Derived files under CC BY-NC 4.0, or provide a fetch script |
| LongMemEval (cleaned) | xiaowu0162 (HF) | MIT (HF dataset card, per the manifest) | Yes | Yes | Yes | No | Fetch script or redistribute |
| Conversation Chronicles | jihyoung (HF) | CC BY 4.0 (manifest) | Yes | Yes | Yes | No | Fetch script or redistribute |
| Multi-Session Chat (MSC) | ParlAI / Meta | **No explicit dataset licence** (manifest; ParlAI code is MIT) | **Do not redistribute** | — | — | Unclear | Rebuild script only |
| Gandalf (hold-out 1) | Lakera | MIT (code) | Yes | Yes | Yes | No | Fetch script |
| deepset prompt injections (hold-out 1) | deepset | CC BY 4.0 (code) | Yes | Yes | Yes | No | Fetch script |
| Mosscap (hold-out 2) | Lakera | MIT (code) | Yes | Yes | Yes | No | Fetch script |
| In-the-wild jailbreak prompts (hold-out 3) | TrustAIRLab | MIT (code) | Yes | Yes | Yes | No | Fetch script. Offensive content |
| **toxic-chat** (hold-out 5) | LMSYS | **CC BY-NC 4.0** (code: `holdout5_corpus.py`) | Yes, NC only | Yes | Yes | **Yes** | Fetch script, or CC BY-NC 4.0 |
| SPML (hold-out 6) | reshabhs (HF) | MIT (code) | Yes | Yes | Yes | No | Fetch script |
| MINJA, AgentPoison, BIPIA, AgentDojo templates | Respective authors | MIT (code: `external_attacks.py`) | Yes | Yes | Yes | No | Fetch script |
| **InjecAgent** | uiuc-kang-lab | **Not recorded in this repository** | Unknown | — | — | Unknown | Verify upstream before release |

### 1.3 Corpora the project generated

| Component | Upstream / owner | Licence / terms | Redistribute? | Modify? | Attribution | Non-commercial? | Proposed treatment |
|---|---|---|---|---|---|---|---|
| LLM-generated attack and benign corpora: own attacks; hold-outs 4, 7, 8; SA-1; SA-2 | Generated with qwen2.5 (Apache-2.0), mistral (Apache-2.0), mistral:7b-text, and gemini-3.5-flash-lite (Google API terms) | Each provider's output terms. **Not reviewed** | To be checked | — | — | The texts describe LoCoMo owners and are built from LoCoMo excerpts, so treat them as LoCoMo-derived (NC) | CC BY-NC 4.0, after checking Gemini's output terms |

### 1.4 Models

| Component | Upstream / owner | Licence / terms | Redistribute? | Modify? | Attribution | Non-commercial? | Proposed treatment |
|---|---|---|---|---|---|---|---|
| qwen2.5:7b | Alibaba Qwen | Apache-2.0 (`ollama show --license`) | Weights not redistributed | — | — | No | Pull from Ollama by digest |
| llama3.1:8b, llama-guard3:8b | Meta | Llama 3.1 Community License (`ollama show --license`, llama3.1) | Weights not redistributed | — | Llama licence terms | No (licence conditions apply) | Pull by digest |
| llama2 | Meta | Llama 2 Community License | Not redistributed | — | — | — | Pull by digest |
| mistral:7b | Mistral AI | Apache-2.0 | Not redistributed | — | — | No | Pull by digest |
| phi3:mini | Microsoft | Microsoft licence (header shown; full text not reviewed) | Not redistributed | — | — | — | Pull by digest |
| HF models: all-MiniLM-L6-v2, nli-deberta-v3-xsmall, ProtectAI deberta-v3-base-prompt-injection-v2, gpt2 | Respective authors | Not inspected in this audit | Not redistributed | — | — | — | Downloaded by name at run time |

### 1.5 Libraries and services

| Component | Upstream / owner | Licence / terms | Redistribute? | Proposed treatment |
|---|---|---|---|---|
| Python libraries | — | torch BSD-3-Clause; transformers Apache-2.0; sentence-transformers Apache-2.0; scikit-learn BSD-3-Clause; numpy BSD/MIT family; scipy BSD; python-docx MIT; openpyxl MIT; networkx BSD-3-Clause; mem0ai Apache-2.0; qdrant-client Apache-2.0; ollama (Python) MIT. Source: package metadata | Not vendored | `requirements-lock.txt` |
| Gemini API (author, judge, adjudicator) | Google | API terms of service | — | Outputs are cached in artifacts. Version not pinnable |

---

## 2. Consequences for release

1. **No single licence can cover the whole repository.**
   - Original code and documentation can take a permissive licence.
   - Any file containing LoCoMo text or toxic-chat text is CC BY-NC 4.0 at most. That includes the stores, evidence, hold-outs 4/7/8, SA-1, SA-2, hold-out 5, and the caches that embed their text.
2. **MSC must not be redistributed.** Its dataset terms are not stated.
3. **InjecAgent's licence must be checked** before its templates are redistributed.
4. **The generated corpora** are both LoCoMo-derived and LLM-generated. Release them as NC, after checking Gemini's output terms.
5. **For anonymous review,** an artifact containing NC data can be shared with reviewers under CC BY-NC 4.0. That is compatible with non-commercial academic review.

---

## 3. Annotation provenance

These are the only human labels used anywhere: the two blind sheets in `docs/phase17/human_labels/`.

### 3.1 Verified from the records

| Item | Verified fact | Evidence |
|---|---|---|
| Number of annotators | 2 | Two sheets, `labelling_sheet.xlsx` and `labelling_sheet_annotator2.xlsx`; `human_label_agreement_annotator2.json` |
| Items | 100 per annotator, the same items: compliance 40, harm 40, mechanism 20 | Sheets ("Label these", 100 rows) |
| Task and instructions | Each sheet has an "Instructions" tab with the question, a YES/NO dropdown, an optional comment, a worked example and a content warning | Instructions tab (read 2026-10-13) |
| Blinding to the judges | Both instructions say not to open `KEY_do_not_open_while_labelling.json`, which holds the judges' answers | Instructions tab |
| Blinding between annotators | Annotator 2's instructions say not to open annotator 1's sheet or the key, and not to discuss items until done | Instructions tab |
| **Annotator 1 is the project owner/author** | Commit `8d02f034` (2026-10-07): "first human check of the LLM judges (60 of 100 items labelled by the owner)" | git log |
| Annotator 2's identity, affiliation, qualifications and relationship to the author | **Not recorded anywhere** in the repository | Searched the sheets, the docs and git |
| File metadata | **Both** workbooks were last saved by the Office user "naisha shetty" (annotator 1 on 2026-10-07, annotator 2 on 2026-10-09). This does not show who annotator 2 was. It does mean the records cannot exclude that annotator 2's sheet was handled on the author's account | `openpyxl` document properties |
| Agreement, as measured by `phase17/human_labels.py` | Annotator 1 vs annotator 2: 95.0% overall (kappa 0.834). Compliance 87.5% (kappa 0.731). Harm 100% (kappa 1.0, at a ceiling: 36/40 YES for both). Mechanism 20/20 YES for both (kappa undefined) | `human_label_agreement_annotator2.json` |
| Adjudication | None between the annotators. Their 5 compliance disagreements were left unresolved and excluded from judge selection ("consensus items") | `compliance_judge_fix.py` |

### 3.2 What this means

- **Annotator 1 was not independent of the research.** They were the author, aware of the hypotheses, though blind to the judges' answers.
- **Annotator 2's independence cannot be verified.**
- So the "human-calibrated" judges (the compliance vote and harm judge J2) are calibrated against labels from **at most one plausibly independent person, possibly zero**.
- Selection used about 20 items per half. Kappa estimates on 20–40 items have wide intervals.
- **Wording for the paper.** "Two annotators, one of whom was an author; the second annotator's independence is not documented." Do not write "independent annotators".
- **Resolved (2026-10-13).** The owner states annotator 2 was their friend, who labelled on the owner's laptop. Use the wording in `ANNOTATION_PROVENANCE_FINAL.md`. (Superseded text: have an unaffiliated annotator label a fresh blind sample.)

### 3.3 Automated adjudication (ADJ-1)

ADJ-1 adds an *automated*, blind adjudicator (Gemini) on a sample of judge disagreements. It is **not** human annotation and is reported as model adjudication only. See `ATTACK_VALIDITY_AND_CAUSALITY_REPORT.md`.
