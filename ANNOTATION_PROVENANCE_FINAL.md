# Annotation Provenance (final)

**Date:** 2026-10-13. Targeted phase, deliverable 4.

**Code:** `phase17/remediation/annotation_provenance.py`.

**Output:** `phase17/data/remediation/annotation_provenance.json`.

No new annotation was commissioned or created. No annotation record was edited.

## 1. Facts, with their source

**Owner's clarification** (stated in chat, 2026-10-13; not recorded in the files themselves):
- **Annotator 1** was the project owner and author.
- **Annotator 2** was the owner's **friend**, who did the labelling **on the owner's laptop**.
- That is why both workbooks were last saved under the owner's Office account ("naisha shetty").

The account name on a file therefore says nothing about who labelled it. It is **not** treated as evidence against annotator 2's labels.

**What the files themselves show:**

| Item | Evidence |
|---|---|
| Same 100 items, same order, fully labelled | Annotator 1: 100/100 YES/NO. Annotator 2: 100/100. Types: 40 compliance, 40 harm, 20 mechanism |
| Annotator 1 labelled first, before the second sheet existed | Commits `8d02f034` and `6229cb00` (2026-10-07). Sheet last saved 2026-10-07 17:57 UTC |
| Annotator 2's sheet as handed over had **no judge verdicts and no annotator-1 labels** | Sheet columns: Item, What you are judging, Question, Memory note, Assistant answer, Your answer, Comment. Commit `4fc400dd`: "blind sheet (same 100 items, no judge verdicts, no first-annotator labels)" |
| Written blinding instructions | Instructions tab: do not open `KEY_do_not_open_while_labelling.json` (the judges' answers) or `labelling_sheet.xlsx` (annotator 1's labels), and do not discuss items with the first annotator until done |
| Labelling window | Sheet generated 2026-10-09 10:52 IST (commit `4fc400dd`); last saved 12:23 IST; labels committed 12:30 IST (`601a4c06`). About 1.5 hours for 100 items |
| Comments | Annotator 1 commented on 4 items, annotator 2 on 6 (optional free-text column) |
| Adjudication between annotators | None. The 5 compliance disagreements were excluded from judge selection, which used only "consensus items" |

## 2. What cannot be established from the records

These are stated as **unknown**, not as failures:

- Whether annotator 2 followed the blinding instructions. The KEY file and annotator 1's sheet were on the same laptop, so blinding was **by instruction, not technically enforced**.
- Whether the owner was present, or discussed items, during the labelling.
- Annotator 2's background, qualifications or prior exposure to the project.
- **Independence from the author.** A friend of the author, labelling on the author's machine, is **not independent of the author** in the sense a reviewer means.

Two further notes:

- **The instructions are not fully neutral.** They describe each row as "one judgement an AI judge already made; you are checking it". No verdict is shown, but the wording invites scrutiny of an AI decision. This applies to both annotators equally.
- **The earlier "independent" wording was unsupported and has been removed.** The commit message of `601a4c06` said "Second independent blind annotator", and the Results-document builder, `compliance_judge_fix.py` and `final_inventory.py` said "two independent blind annotators". The code wording is corrected in this phase. Commit messages are history and are left as they are.

## 3. Agreement, with uncertainty

Item-bootstrap 95% CIs, 10,000 resamples.

| Comparison | n | Agreement | κ | 95% CI |
|---|---|---|---|---|
| Annotator 1 vs 2, all items | 100 | 95% | 0.834 | 0.669–0.962 |
| Annotator 1 vs 2, compliance | 40 | 87.5% | 0.731 | 0.484–0.939 |
| Annotator 1 vs 2, harm | 40 | 100% | 1.0 | Ceiling: 36/40 YES for both |
| Annotator 1 vs 2, mechanism | 20 | 100% | undefined | All YES |
| Original compliance judge (C0) vs annotator 1 | 40 | 75% | 0.50 | 0.22–0.75 |
| Original compliance judge (C0) vs annotator 2 | 40 | 77.5% | 0.55 | 0.30–0.79 |
| Original harm judge (J0) vs either annotator | 40 | 60% | 0.20 | 0.05–0.41 |

## 4. Which claims the labels can support

| Project claim | Depends on the human labels? | Supported by this annotation? |
|---|---|---|
| Defence detection and false-positive rates (B12, B13, LOO, hold-outs) | **No.** No judge, no human label | Not applicable |
| The memory's net effect is positive and large | **No.** Shown under C0, which was not human-selected (+43.2), and under the vote (+47.1) | Not needed |
| Defence ranking is stable across working-attack definitions | **No.** Identical under C0, the vote and "robust" | Not needed |
| The original harm judge (J0) under-counts harm | **Yes** | **Yes, as a limited claim.** Two people, labelling separately by instruction, both disagree with J0 in the same direction on the same items (κ 0.20) |
| The compliance vote is better calibrated than C0 | **Yes.** It was selected on 35 consensus items | **Weakly.** 35 items; the selection improvement was not significant (5 fixed vs 2 broken, p = 0.45) |
| J2 is a "human-validated" harm judge | **Yes.** Selected on annotator 1's labels | **Weakly.** Annotator 2's harm labels are identical at a 90% YES ceiling, so this *replicates* rather than independently re-tests the selection |

### Wording for the paper

> "Two annotators labelled 100 items: the first author, and a second annotator known to the author who labelled separately, following written instructions not to view the first annotator's labels or the judges' outputs. Neither is independent of the author. Judge-dependent levels are therefore reported under two judges, and no defence or ranking result depends on human labels."

## 5. Is another annotation study needed?

**Not by default, and not because of the file account.** The annotation is used only to choose between LLM judges and to show that the original harm judge under-counts harm. Every defence, ranking and net-effect conclusion is shown to be judge-robust **without** it.

**One specific, material question it cannot answer.** Suppose a reviewer requires the **harm levels** (the absolute undefended-harm rate under J2) to rest on labels independent of the author. Then only an annotator unconnected to the author would answer that, because the J2 selection rests on the author's own labels.

If the paper reports harm levels only as "under J0 and J2, with J0 known to under-count", **no further annotation is required** for the claims as written.
