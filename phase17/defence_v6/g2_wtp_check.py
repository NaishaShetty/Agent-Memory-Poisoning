"""Corrects g2_eval.json's condition-B entry, which asserted item-for-item equality with A through a placeholder
(all(True ...)) instead of computing it. Recomputes B (write-time taint + HFP-B) step by step from cached features."""
import json

from phase17.defence_v6 import g2_eval as G
from phase17.defence_v6.fpb import SEL_B
from phase17.stats import rate_with_ci

sb = json.loads(SEL_B.read_text(encoding="utf-8"))["chosen"]
M = ("B", sb["tau_n"], sb["tau_r"])
F = G.Feat()
rs = G.rows(F)
A = [r for r in rs if r["kind"] == "atk" and r["flagged"]]
w = {r["key"]: G.wtp_hfp(r, M) for r in A}
eq = sum(w[r["key"]] == [G._hfp_row(r, k, M) for k in range(G.GENS)] for r in A)
out = {"condition": "B_never_persisted_WTP_HFP-B (recomputed)", "item_for_item_equal_to_A": f"{eq}/{len(A)}",
       "withheld_carrying_g4": rate_with_ci(sum(w[r["key"]][3] for r in A if r["carry"][3]), sum(r["carry"][3] for r in A)),
       "note": "replaces the placeholder entry in g2_eval.json recovery_HFP-B.B_never_persisted_WTP_HFP"}
(G.DATA / "g2_wtp_check.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print(out)
