# -*- coding: utf-8 -*-
"""Fold the last four results into the inventory's classification."""
import pathlib

p = pathlib.Path("phase17/final_inventory.py")
s = p.read_text(encoding="utf-8")
if "neutralise.json" in s:
    raise SystemExit("already applied")

s = s.replace(
    '''    add("favourable", "Recommendation conditioned on the false-positive budget",''',
    '''    nv, n2 = _L("neutralise.json"), _L("neutralise_v2.json")
    if nv:
        pa = nv["paired_attack_compliance"]
        add("favourable", "NEUTRALISATION resolves the one regime detection could not",
            f"hold-out 3 attack compliance {pct(nv['attack_compliance_raw']['rate'])} -> "
            f"{pct(nv['attack_compliance_neutralised']['rate'])}, paired +{pa['only_a']}/"
            f"-{pa['only_b']}, p={pa['p_exact']:.2g}, with no significant change in benign "
            f"information use; nothing is excluded so the false-positive rate is zero by "
            f"construction",
            "neutralise.json + neutralise_v2.json",
            "the active ingredient is recency alone; v2/v3/v5 are indistinguishable at n=120 "
            "given a ~5-point noise floor, and the frame this project first built is actively "
            "harmful")
    ca = _L("eval_calibration2.json")
    if ca:
        add("favourable", "Prediction calibration demonstrated, not asserted",
            f"{ca['n_held']}/5 pre-registered predictions held on an unmeasured target "
            f"(B17/B18 on hold-out 2), with intervals committed before the run",
            "eval_calibration2.json + PREREGISTRATION_2_CALIBRATION.md",
            "it does not un-fail the three that failed in the first pre-registration")
        m = ca["measured"]["B18"]
        add("favourable", "New best on hold-out 2",
            f"B18 reaches {pct(m['recall']['rate'])} against B14's 54.2%, at "
            f"{m['ordinary_benign_fpr']['k']}/1054 ordinary-benign false positives",
            "eval_calibration2.json",
            "B17/B18 postdate the hold-out results that informed their design, so this is not a "
            "clean generalisation estimate")
    er = _L("error_registry.json")
    if er:
        add("favourable", "Every past error's guard PROVEN by mutation testing",
            f"{er['n_proven']}/{er['n']} guards fail when their error is reintroduced and pass "
            f"again once restored",
            "error_registry.json",
            "establishing it exposed that four of eight guards had been decoration, plus CRLF "
            "shell scripts, a guard passing on exit 127, and the harness corrupting what it "
            "measured twice")
    ab = _L("b14_ablate_deberta.json")
    if ab:
        v = ab["variants"]
        full = v["full_11_features"]["holdout_gap_points"]
        less = v["without_deberta_pi"]["holdout_gap_points"]
        add("unfavourable", "My 'instability inherited from deberta' attribution was imprecise",
            f"removing the feature WIDENS the cross-corpus gap ({full:+.1f} to {less:+.1f}) and "
            f"costs recall everywhere, hold-out 2 collapsing 59.8% to 40.7%; the gap is a "
            f"property of the fused weights and the feature is load-bearing",
            "b14_ablate_deberta.json",
            "still consistent with B18: a fusion can under-use a feature it contains, which is a "
            "different claim from that feature causing the instability")
    if n2:
        add("unfavourable", "The neutralisation frame I originally built is actively harmful",
            "v1_prefix raises attack compliance 6.7 points and costs 10 points of benign "
            "utility; the earlier 'partial, 49/150 -> 38/150' reading came from a hold-out "
            "sample that flattered it",
            "neutralise_v2.json")
    add("favourable", "Recommendation conditioned on the false-positive budget",''')

# The FPR row is no longer wholly unresolved: neutralisation addresses that regime.
s = s.replace(
    '''            "every FPR previously published used benign text unlike the attack distribution")''',
    '''            "every FPR previously published used benign text unlike the attack distribution; "
            "detection cannot fix this (B19 failed, 32.44) but neutralisation addresses the "
            "regime on a different axis at zero false-positive cost (32.46)")''')
p.write_text(s, encoding="utf-8")
print("inventory updated with the final four results")
