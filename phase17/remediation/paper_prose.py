"""Outcome-neutral prose for the paper's SA-1 / P2 passages, generated from the scored artifacts.

Every sentence states a measured quantity and, where one exists, the pre-registered prediction's HELD/FAILED
status. No sentence is chosen by whether a result is favourable. Used by `paper_numbers.py`.
"""
from __future__ import annotations

from typing import Dict, List


def _f(d: Dict) -> str:
    return f"{d['k']}/{d['n']}"


def _p(x) -> str:
    return "n/a" if x is None else (f"{x:.2g}" if x >= 1e-3 else f"{x:.1e}")


def _st(preds: List[Dict], pid: str) -> str:
    p = next(x for x in preds if x["id"] == pid)
    return f"{pid}~{p['status']}"


def _holm(ps: List[tuple]) -> List[tuple]:
    m = len(ps)
    order = sorted(range(m), key=lambda i: ps[i][1])
    adj, running = [0.0] * m, 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * ps[i][1]))
        adj[i] = running
    return [(ps[i][0], ps[i][1], adj[i]) for i in range(m)]


def prose(sa: Dict, p2: Dict) -> Dict[str, str]:
    R = sa["by_judge"]["C0"]
    A, L, D = R["atk"], R["ben"], R["discrimination"]
    Ad, Ld = A["defended"], L["defended"]
    pr = sa["predictions"]
    V = sa["by_judge"]["vote"]["atk"]

    sa_abs = (f"a pre-registered experiment with 60 conditional backdoors and 60 benign conditional lookalikes found "
              f"activation on a natural trigger in {_f(A['activation_on_trigger'])} attacks and on an unrelated message "
              f"in {_f(A['activation_on_non_trigger'])}; admission-time content detection excluded "
              f"{D['B12']['attack_excluded']}/60 attacks and {D['B12']['lookalike_excluded']}/60 lookalikes before "
              f"activation---because these backdoors state their malicious action explicitly, not because any "
              f"sleeper-specific signal worked (a dedicated sleeper guard flagged "
              f"{Ad['sleeper_guard_phase8']['excluded']['k']}/60).")
    sa_body = (
        f"Each of 60 conditional backdoors and 60 benign conditional lookalikes (same author, owner, prompt and "
        f"third-person syntax) carries a natural trigger message and an unrelated message. The note was retrieved "
        f"into the agent's top five by its trigger in {_f(A['retrieved_on_trigger'])} attacks and "
        f"{_f(L['retrieved_on_trigger'])} lookalikes, and by the unrelated message in "
        f"{_f(A['retrieved_on_non_trigger'])} and {_f(L['retrieved_on_non_trigger'])}. "
        f"Undefended, attacks activated (complied with the note present, not without it) on "
        f"{_f(A['activation_on_trigger'])} trigger messages and {_f(A['activation_on_non_trigger'])} unrelated "
        f"messages ({_st(pr, 'SA-1')}, dormancy; {_st(pr, 'SA-2')}, paired "
        f"+{A['paired_T_present_vs_absent']['only_a']}/$-${A['paired_T_present_vs_absent']['only_b']}, "
        f"$p$={_p(A['paired_T_present_vs_absent']['p_exact'])}); under the human-calibrated vote judge, "
        f"{_f(V['activation_on_trigger'])} and {_f(V['activation_on_non_trigger'])}. "
        f"Lookalikes, whose activation is the intended behaviour, activated on {_f(L['activation_on_trigger'])} triggers. "
        f"At admission, before any activation, B13 on the untrusted channel excluded "
        f"{D['B13_untrusted']['attack_excluded']}/60 attacks and {D['B13_untrusted']['lookalike_excluded']}/60 "
        f"lookalikes ({_st(pr, 'SA-3')}, Fisher $p$={_p(D['B13_untrusted']['fisher_p_greater'])}); B12 "
        f"{D['B12']['attack_excluded']} and {D['B12']['lookalike_excluded']} ({_st(pr, 'SA-4')}). B13 reduced trigger "
        f"activation from {_f(A['activation_on_trigger'])} to {_f(Ad['B13_untrusted']['activation_on_trigger'])} "
        f"({_st(pr, 'SA-5')}, $p$={_p(Ad['B13_untrusted']['paired_vs_undefended']['p_exact'])}) and lookalike "
        f"activation from {_f(L['activation_on_trigger'])} to {_f(Ld['B13_untrusted']['activation_on_trigger'])}. On "
        f"the user channel B13 excluded {Ad['B13_user']['excluded']['k']} attacks, by construction. The dedicated Phase~8 "
        f"sleeper guard flagged {_f(Ad['sleeper_guard_phase8']['excluded'])} attacks ({_st(pr, 'SA-6')}); the "
        f"development-fitted anomaly signal flagged {_f(Ad['anomaly_devfit_p90']['excluded'])} attacks and "
        f"{_f(Ld['anomaly_devfit_p90']['excluded'])} lookalikes ({_st(pr, 'SA-7')}); deberta flagged "
        f"{_f(Ad['deberta_pi_v2@dev']['excluded'])} and {_f(Ld['deberta_pi_v2@dev']['excluded'])}. At activation "
        f"time, the instruction-aware frame changed attack activation from {_f(A['activation_on_trigger'])} to "
        f"{_f(A['activation_on_trigger_v6_frame'])} ({_st(pr, 'SA-8')}, $p$="
        f"{_p(A['paired_v6_vs_unframed_activation']['p_exact'])}) and lookalike activation from "
        f"{_f(L['activation_on_trigger'])} to {_f(L['activation_on_trigger_v6_frame'])} ({_st(pr, 'SA-9')}). "
        f"The interpretation matters: B12 alone excluded every attack, so detection here rests on the explicit "
        f"payload (a named outside company and a covert action), not on dormancy; mundane, instruction-free sleeper "
        f"notes are not caught by content detection (0\\% on the project's sleeper family) and only partly by "
        f"corroboration. B13's corroboration thresholds were calibrated on this owner's conversation among others "
        f"(\\S\\ref{{sec:limits}}).")

    o = p2
    W, NC = o["withheld_payload_carrying_gen2"], o["withheld_non_carrying_gen2"]
    pp = o["predictions"]
    p2_abs = (f"carried the payload into a second consolidation in {_f(o['payload_carried_gen2'])} instances; "
              f"containing those second-generation summaries depends on inheriting the intermediate summary's "
              f"state (withheld carrying summaries: {_f(W['S-inh'])} with inheritance, {_f(W['S-noinh'])} without).")
    p2_body = (
        f"Second-generation summaries carried the poison's payload in {_f(o['payload_carried_gen2'])} instances "
        f"({_f(o['carried_gen2_given_gen1'])} of those whose first summary carried it; {_st(pp, 'P2-1')}). Serving them on "
        f"B13-excluded instances produced harm in {_f(o['harm_gen2_on_b13_excluded']['A0'])} "
        f"({_st(pp, 'P2-4')}). Of the {W['S-inh']['n']} carrying summaries of excluded poisons, containment withheld "
        f"{_f(W['L-inh'])} (lexical), {_f(W['S-inh'])} (semantic, inheriting the parent's state), "
        f"{_f(W['S-inh+d2'])} (adding grandparents) and {_f(W['S-noinh'])} (grandparents only, no inheritance; "
        f"{_st(pp, 'P2-3')}); {_st(pp, 'P2-2')}. The semantic inheriting arm also withheld {_f(NC['S-inh'])} summaries "
        f"that did not carry the payload ({_st(pp, 'P2-5')}) and {_f(o['benign_collateral_gen2']['S-inh'])} benign "
        f"chains. Harm with each arm: " + ", ".join(f"{k} {_f(v)}" for k, v in o["harm_gen2_on_b13_excluded"].items())
        + f". No arm acts on the {o['b13_missed_no_arm_can_act']['n']} instances admission missed, "
        f"{o['b13_missed_no_arm_can_act']['carry2']} of whose second summaries still carry the payload.")

    fam = [(x["id"], x["p"]) for x in pr + pp if x.get("kind") == "significance" and x.get("p") is not None]
    hol = _holm(fam)
    rem = ("Holm-adjusted $p$: " + "; ".join(f"{i} {_p(a)}" for i, _, a in hol) + ".") if hol else "no significance predictions."

    concl = (
        "Re-scoring defenses on attacks shown to work changes the measured recall by up to \TwoDenMaxShift{} points in either "
        "direction, so validity filtering belongs in memory-poisoning evaluation. For admission, corroborating "
        "untrusted personal claims against the owner's conversation reached memory poisoning that content classifiers "
        "missed on three single-use hold-outs, at a benign cost, while the channel label itself added nothing and "
        "left the user channel unprotected. For propagation, retention-based lineage taint acts only on descendants "
        f"of poisons admission already caught; at the second generation it withheld {_f(W['S-inh'])} carrying "
        f"summaries when the intermediate summary inherited its state and {_f(W['S-noinh'])} when it did not. "
        "For sleeper rules, "
        f"SA-1 confirmed dormancy and natural trigger activation, and showed that conditional rules with an explicit "
        f"malicious action are stopped before activation by content detection ({D['B12']['attack_excluded']}/60) "
        f"with little cost to benign conditional rules ({D['B12']['lookalike_excluded']}/60); no sleeper-specific "
        "signal worked, and stealthy, instruction-free sleepers remain largely undetected. Each conclusion holds within an in-context evaluation harness, a 7B agent and "
        "evaluator-assigned channels, and should be re-tested in a production memory system.")
    return {"SAoneAbstract": sa_abs, "SAoneBody": sa_body, "PtwoAbstract": p2_abs, "PtwoBody": p2_body,
            "RemHolm": rem, "Conclusion": concl}
