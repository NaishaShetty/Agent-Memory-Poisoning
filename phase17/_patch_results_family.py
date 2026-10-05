# -*- coding: utf-8 -*-
"""One-shot patch: add the per-family sections (5A/5B) to the results-analysis builder."""
import pathlib

p = pathlib.Path("phase17/build_results_analysis_docx.py")
s = p.read_text(encoding="utf-8")

if "5A. Results by Attack Family" in s:
    raise SystemExit("already patched")

s = s.replace(
    'SIM090 = L("eval_rejection_memory_sim090_EXPLORATORY.json")',
    'SIM090 = L("eval_rejection_memory_sim090_EXPLORATORY.json")\n'
    'FAM = L("family_breakdown.json")\n'
    'EVID = L("evidence_round6.json")\n'
    'EVID5 = L("evidence_available_check.json")')

NEW = '''H("5A. Results by Attack Family, Including the Seven Founding Families", 1)
P("Every other table in this analysis is organised by CORPUS, because that is how the "
  "populations were built and frozen. The seven founding families this benchmark reconstructs "
  "from the literature -- AgentPoison, MINJA, FARMA, MemoryGraft, DSRM, MPBench-PCFI and sleeper "
  "memory poisoning -- are spread across those corpora, so a reader looking for a specific "
  "family could previously find its detection rate only in the harm table. This section reports "
  "each family by name.")
if FAM:
    def _c(v, c):
        if c not in v:
            return "-"
        f = v[c]["full"]["rate"]
        w = v[c]["working"]["rate"] if v[c].get("working") else None
        return ("%.0f%% / " % (100 * f)) + (("%.0f%%" % (100 * w)) if w is not None else "-")

    rows = [["Attack family", "Instances", "Mechanism-correct", "Working rate",
             "B12 full/working", "B13 full/working", "B14 full/working", "B17 full/working"]]
    for fams in (FAM["founding_families"], FAM["mechanism_families"]):
        for f in fams:
            v = FAM["families"].get(f)
            if not v:
                rows.append([f, "absent", "-", "-", "-", "-", "-", "-"])
                continue
            mc = v.get("mechanism_correct")
            rows.append([f + (" *" if v["is_founding"] else ""), v["n_instances"],
                         ("%.0f%%" % (100 * mc["rate"])) if mc else "-",
                         "%.0f%%" % (100 * v["working_rate"]),
                         _c(v, "B12"), _c(v, "B13"), _c(v, "B14"), _c(v, "B17")])
    TBL(rows)
    CAP("Table 5A. Per-family results. * marks the seven founding families. Mechanism-correct is "
        "the share of instances a third model family judges to implement the mechanism they are "
        "labelled with; working rate is the share that causally subvert an undefended agent AND "
        "implement their label. Detection is full-population / working-attack. Source: "
        "phase17/data/family_breakdown.json, a join over existing artifacts with no model "
        "re-run. IMPORTANT: the detection columns are a FLOOR -- see Section 5B.")
    P("Read at face value this table is unflattering, and the unflattering parts are real in "
      "differing degrees. Of the seven founding families only FARMA (74% full, 82% working) and "
      "AgentPoison (59%, and 86% on working attacks for the fusion configurations) are well "
      "detected. DSRM, MPBench-PCFI, MINJA and MemoryGraft sit between 11% and 32%, and sleeper "
      "memory poisoning is at 0% under every configuration including on its 24 working "
      "instances. The later mechanism families are detected far better -- policy revocation 98%, "
      "authority impersonation 82%, conditional backdoor 52% -- which is the expected shape, "
      "since those are the classes the defense stack was designed against while the founding "
      "families are the independent test of it.")
    P("The sleeper result has an identifiable cause rather than being a brute failure. That "
      "attack is designed to be a mundane, harmless-looking statement about a person's routine "
      "with no instruction in it, and its mechanism check requires exactly that; it is 100% "
      "mechanism-correct and 63% working, so the instances are valid and they function. A "
      "content-only detector that flagged such a note would also flag the benign personal notes "
      "that constitute most of a real memory store, so a 0% content-only rate here is the attack "
      "succeeding at what it was built for rather than a defect in the detector. It is also "
      "precisely the class that provenance and corroboration exist to reach, which is the "
      "subject of the next section.")
else:
    MISSING.append("family_breakdown.json")

H("5B. These Detection Rates Are a Floor: Corroboration Was Switched Off", 1)
P("The B12 and B13 columns of Table 5A are identical for all seven founding families, and that "
  "is not a coincidence. The evaluation producing them supplies provenance SOURCES but no "
  "corroboration EVIDENCE, so B13's NLI check of personal claims against the owner's own "
  "conversation -- the signal that reaches additive fabrication at 37/72 in the pre-registered "
  "comparison of Table 3 -- never fires. Every B13, B14, B15 and B17 figure in the "
  "corpus-oriented tables of this analysis is therefore a FLOOR for the provenance-aware "
  "configurations. The previous round established this and labelled its own numbers as floors; "
  "the label was not carried into per-family reporting, where its absence reads as a flat "
  "detection failure.")
if EVID5:
    rows = [["Population", "Configuration", "No evidence", "With the real conversation",
             "Exact test"]]
    for pop, v in EVID5["populations"].items():
        for c, x in v.items():
            if isinstance(x, dict) and "no_evidence" in x:
                rows.append([pop, c, kn(x["no_evidence"]), kn(x["with_evidence"]),
                             "p = %.4g" % x["paired"]["p_exact"]])
    TBL(rows)
    CAP("Table 5B. The size of what is switched off, measured on the three populations whose real "
        "conversation exists. Evidence is %s turns of the actual owner conversation (speakers %s), "
        "not anything constructed for the test. Source: "
        "phase17/data/evidence_available_check.json."
        % (EVID5.get("n_evidence_turns"), ", ".join(EVID5.get("speakers", []))))
    P("On the evasion population -- 47 defense-aware rewrites stuck at 4/47 for every "
      "configuration across three rounds, and reported as the ceiling of content-only detection "
      "-- supplying the conversation takes B13 from 4/47 to 28/47 (p<0.0001). That is the largest "
      "single detection improvement in this project, and it comes from making a signal available "
      "rather than from changing a detector.")
if EVID:
    rows = [["Attack family", "Instances"] + ["%s: no ev. -> with ev." % c for c in EVID["configs"]]]
    for f, v in EVID.get("by_family", {}).items():
        cells = []
        for c in EVID["configs"]:
            if c in v:
                cells.append("%d -> %d (p=%.3g)" % (v[c]["no_evidence"]["k"],
                                                    v[c]["with_evidence"]["k"],
                                                    v[c]["paired"]["p_exact"]))
            else:
                cells.append("-")
        rows.append([f, v["n"]] + cells)
    TBL(rows)
    CAP("Table 5C. Every own-attack family re-scored with the real conversation supplied. Source: "
        "phase17/data/evidence_round6.json.")
    rows = [["Configuration", "Own attacks, no evidence", "Own attacks, with evidence",
             "Ordinary-benign FPR, no evidence", "Ordinary-benign FPR, with evidence"]]
    for c, v in EVID.get("aggregate", {}).items():
        rows.append([c,
                     pct(v["attacks_no_evidence"]["rate"]) if v.get("attacks_no_evidence") else "-",
                     pct(v["attacks_with_evidence"]["rate"]) if v.get("attacks_with_evidence") else "-",
                     kn(v["ordinary_benign_no_evidence"]) if v.get("ordinary_benign_no_evidence") else "-",
                     kn(v["ordinary_benign_with_evidence"]) if v.get("ordinary_benign_with_evidence") else "-"])
    TBL(rows)
    CAP("Table 5D. The recall gain with its false-positive cost measured on the SAME footing. "
        "Supplying an owner conversation makes every claim about a person who does not appear in "
        "it uncorroborated, which is real signal against an invented-persona attack and equally a "
        "real risk to a benign note about someone the conversation never mentions; a recall gain "
        "reported without this column would be meaningless.")
else:
    MISSING.append("evidence_round6.json")
    P("A full per-family re-scoring with evidence supplied is specified in "
      "phase17/evidence_round6.py and had not completed when this document was generated. It "
      "scores every own-attack family with the real conversation available AND the benign "
      "populations with the same evidence, so the recall gain is reported with its false-positive "
      "cost on the same footing; if the false-positive rate rises as much as recall there is no "
      "gain, and the artifact records that outcome rather than the favourable half of it.")
P("What this does not fix: the external injection corpora have no owner conversation, and their "
  "attacks are not claims about a person, so there is nothing to corroborate. Evidence is "
  "inapplicable there by construction, which means the provenance configuration's weak showing "
  "on those corpora is genuine rather than an artifact -- and it is the reason the union "
  "configurations of Section 7.1 exist.")

'''

anchor = 'H("6. RQ3 - Generalisation Across Independently Authored Corpora", 1)'
assert anchor in s
s = s.replace(anchor, NEW + anchor, 1)
p.write_text(s, encoding="utf-8")
print("patched results builder with sections 5A/5B")
