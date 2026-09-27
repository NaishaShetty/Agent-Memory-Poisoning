"""Live utility campaign for B12 vs B0/B9/B10 (same harness/model/sizes as
Phase 14/15; B0 is re-run in the same run so comparisons are in-run, since the
local model is not perfectly deterministic)."""
from pathlib import Path

from phase14 import campaign
from phase14.defended_retrieval import (
    CONFIG_B0_NO_DEFENSE, CONFIG_B9_RISK_COMPOSED, CONFIG_B10_LEARNED_HYBRID, CONFIG_B12_STACKED,
)

campaign.UTILITY_PILOT_CONFIGS = (CONFIG_B0_NO_DEFENSE, CONFIG_B9_RISK_COMPOSED, CONFIG_B10_LEARNED_HYBRID, CONFIG_B12_STACKED)
if __name__ == "__main__":
    campaign.run_full_pilot(out_path=Path(__file__).parent / "data" / "utility_b12.json")
    print("DONE")
