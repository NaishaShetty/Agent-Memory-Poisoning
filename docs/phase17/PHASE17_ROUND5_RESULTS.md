# Phase 17 — external review round 5 (2026-09-30)

Round 4 ended with the finding that made this round necessary: measured against published
detectors, **B12's advantage is 2.80x on attacks this project wrote and 1.03x — none — on
attacks written by other projects** ([`PHASE17_REVIEW4_RESULTS.md`](PHASE17_REVIEW4_RESULTS.md)
§8). The brief for round 5 was to build a defense that clearly beats published baselines on
attacks this project did **not** write, with the independent set as the headline.

This document reports what was built and what it measured, including where it fell short.
Read §7 first if you only want the honest summary.

---

## 1. What counts as held out now, and why the old external set no longer does

Round 4 measured B12 and B13 on all 266 attacks in `external_attacks.py` and published the
per-source breakdown. A defense designed after reading those numbers cannot honestly call
that population held out, whatever the code does. So:

| Population | Role from round 5 onwards |
|---|---|
| `external_attacks.py` (266: MINJA, AgentPoison, InjecAgent, BIPIA, AgentDojo) | **external-DEV** — B14 is fitted on it |
| `external_test_corpus.py` (1,258 attacks + 393 benign) | **external-TEST** — frozen, never trained or thresholded on |
| this project's own attack populations | evaluation only, never in B14's training |

**external-TEST was frozen before any round-5 defense code was written**, with a SHA-256
recorded in `data/external_test_freeze.json` and a CI test that recomputes it. Its two
sources:

- **`Lakera/gandalf_ignore_instructions`** (MIT) — 998 attacks typed by **real human players**
  of the Gandalf game. These are the first genuinely human-authored attacks anywhere in
  MAMBench; every other attack text in this project is LLM-generated. For this population,
  the attack-side authorship confound that `PHASE17_CURRENT_RESULTS.md` §5 has carried open
  since round 2 is **closed**.
- **`deepset/prompt-injections`** (CC-BY-4.0) — 260 attacks and 393 benign items, so the
  false-positive side also gets an externally-authored control.

**Limits of this test set, stated before its numbers rather than after.** Both are
*prompt-injection* corpora, not memory-poisoning corpora. Gandalf in particular is dominated
by one narrow, overt goal (make the model reveal a password): "Ignore all previous text..."
is typical. A strong score on external-TEST is evidence about **detecting overt injected
instructions that arrive in memory**, and is *not* evidence about subtle memory poisoning
such as additive fabrication or preference hijack. The populations that test those are this
project's own and the provenance fabrications in
[`PHASE17_REVIEW4_RESULTS.md`](PHASE17_REVIEW4_RESULTS.md) §6.

## 2. Diagnosis: what B12 was actually keying on

Decomposing B12's score into its two components — a 384-dim bge-small text embedding and a
zero-shot judge logit — on attacks whose style it has and has not seen:

| Population | embedding part | judge part | total | excluded |
|---|---|---|---|---|
| own attacks (qwen + gemini) | **+1.09** | −1.22 | +3.08 | 51.4% |
| externally-authored attacks | **−0.27** | −1.51 | +1.43 | 33.8% |
| — InjecAgent | +0.85 | −0.38 | +3.67 | 67.7% |
| — BIPIA | −1.13 | −2.58 | −0.51 | 8.0% |
| benign (dataset_arena) | −2.59 | −4.39 | −3.77 | 0.0% |

**The embedding term carries essentially the whole own-vs-external gap — 1.36 logits — while
the judge term differs by 0.29.** The component that reasons about what a note *does*
transfers across authorship; the component that encodes lexical and topical surface is what
was fitted to this project's house style. That is the mechanism behind round 4's headline,
and it is what B14 is designed around.

A second measurement pointed the same way: B12's errors and the published detectors' errors
are substantially **complementary** on external-dev.

| | caught on external-dev (266) |
|---|---|
| B12 alone | 90 |
| Llama Guard 3 alone | 87 |
| plain "is this malicious?" prompt (qwen) alone | 71 |
| **B12 ∪ plain prompt** | **125** |
| **B12 ∪ all three baselines** | **147** |

## 3. B14 — the round-5 defense

`phase17/b14_live.py`. B12 and B13 are both left unchanged, so their published numbers stay
valid.

1. **The raw text embedding is removed** — directly from §2's diagnosis — and replaced by a
   calibrated fusion over eleven signals that each describe a note's intent or effect: this
   project's zero-shot judge, **three published detectors** (Llama Guard 3, ProtectAI
   deberta-v3 prompt-injection v2, a GPT-2 perplexity filter), plain "is this malicious?"
   prompts on **two** model families, the steer/lineage/worm judge tiers, and two cheap
   lexical priors.
2. **Everything structural from B13 is kept**: source-aware trust, NLI corroboration of
   unsupported personal claims, the unsupported-preference rule, and the carry-forward write
   guard. These are style-independent by construction, which is why they survived round 4.
3. **Fitted on dev only** (`train_b14.py`): the designated dev pool, external-DEV, and
   AgentDojo's dev benign half (so the model cannot learn "not a user turn ⇒ attack").
   Thresholds from group-held-out out-of-fold scores at 0.5%/2% FPR on dev negatives — the
   same protocol B12 used.

B14 refuses to score at all if its fitted model file is absent, rather than falling back to
uncalibrated weights, since that would silently be a different defense.

**Including published detectors inside B14 means "B14 beats Llama Guard 3" is partly a
superset relation, not a fair fight.** The number that carries real information is B14's
gain over its own best single component, and that is reported alongside.

## 4. Attack validity: are these attacks even working?

*(filled in from `phase17/attack_validity_audit.py`)*

## 5. The round-5 comparison

*(filled in from `phase17/eval_round5.py`: own / external-dev / external-TEST /
leave-one-source-out / adaptive, with CIs, FPR, utility and cost)*

## 6. A dev/test leak found and fixed during this round

`phase17/tests/test_review5_fixes.py` was written to hunt for leakage and immediately found
one: the AgentDojo benign extract assigned dev/test by row index over a list containing
duplicate environment entries (a weekly "yoga class" calendar event, near-identical
transactions), so 4 of 74 rows were duplicates and **one text appeared in both halves**.
Small, but exactly the class of defect that invalidates a held-out number.

Fixed by moving the extraction into `phase17/agentdojo_benign.py` (it had been an inline
shell script, i.e. not reproducible from the repo at all), deduplicating on normalized text
**before** splitting, and splitting deterministically over sorted unique texts: 74 raw → 69
unique → 35 dev / 34 test. The one affected number in the round-4 frozen evaluation was
re-scored and the correction is recorded inside `data/frozen_eval_b13.json` itself.

## 7. Honest summary

*(filled in last, after §5)*
