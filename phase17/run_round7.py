"""Round 7 GPU queue: one stage at a time, orphans killed between stages, logs per stage.

The same discipline as `run_all.py` -- two jobs on a 6GB card stall each other -- applied to the
round-7 stages, which `run_all` does not know about. A stage that fails stops the queue; nothing
downstream runs on a partial input. Every stage checkpoints, so re-running the queue resumes.

    python -m phase17.run_round7 dev          # dev features -> dev_round7 -> compose_dev
    python -m phase17.run_round7 exfil        # exfiltration authoring (qwen gens + scoring)
    python -m phase17.run_round7 ho4causal    # hold-out 4 causal validity
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "phase17" / "data" / "run_all_logs"
KILL = ROOT / "scripts" / "kill_orphan_phase17.ps1"

QUEUES = {
    "dev": [
        ("precompute_dev_benign", [sys.executable, "-u", "-c",
                                   "from phase17.precompute_features import run;"
                                   "from phase17.toxicchat_dev_benign import dev_benign_texts;"
                                   "run(dev_benign_texts())"]),
        ("dev_round7", [sys.executable, "-u", "-m", "phase17.dev_round7"]),
        ("compose_dev", [sys.executable, "-u", "-m", "phase17.compose_dev"]),
    ],
    "exfil": [("exfil_authoring", [sys.executable, "-u", "-m", "phase17.exfil_authoring"])],
    "ho4causal": [("holdout4_causal", [sys.executable, "-u", "-m", "phase17.holdout4_validity",
                                       "causal"])],
    # The ONE scoring of hold-outs 4 and 5; refuses unless the pre-registration is committed.
    "holdouts": [("eval_round7_holdouts", [sys.executable, "-u", "-m", "phase17.eval_round7_holdouts"])],
    "ho7causal": [("holdout7_causal", [sys.executable, "-u", "-m", "phase17.holdout7_validity", "causal"])],
    "holdouts67": [("eval_round7b_holdouts", [sys.executable, "-u", "-m", "phase17.eval_round7b_holdouts"])],
    "ho5causal": [("holdout5_causal", [sys.executable, "-u", "-m", "phase17.holdout5_causal"])],
    "sweep": [("ledger_radius_sweep", [sys.executable, "-u", "-m", "phase17.eval_ledger_radius_sweep"])],
    # The items 1-14 follow-up (round 7, 2026-10-07), in GPU order.
    "items": [
        ("holdout7_build", [sys.executable, "-u", "-m", "phase17.holdout7_corpus"]),
        ("neutralise_utility", [sys.executable, "-u", "-m", "phase17.neutralise_utility"]),
        ("noise_repeats", [sys.executable, "-u", "-m", "phase17.noise_repeats"]),
        ("adaptive_round7", [sys.executable, "-u", "-m", "phase17.adaptive_round7"]),
        # LAST: it needs the remote Gemini collection to have finished, and if it has not it
        # stops -- which must not block the GPU stages before it.
        ("harm_strong_judge", [sys.executable, "-u", "-m", "phase17.harm_strong_agent", "judge"]),
    ],
    # single-stage queues, so the follow-up work can be reordered without editing "items"
    "noise": [("noise_repeats", [sys.executable, "-u", "-m", "phase17.noise_repeats"])],
    "utility": [("neutralise_utility", [sys.executable, "-u", "-m", "phase17.neutralise_utility"])],
    "adaptive": [("adaptive_round7", [sys.executable, "-u", "-m", "phase17.adaptive_round7"])],
    "harmjudge": [("harm_strong_judge", [sys.executable, "-u", "-m", "phase17.harm_strong_agent", "judge"])],
    # Harm-judge fix: the local candidate (J1) needs the GPU, then the re-measurement.
    "harmfix": [("harm_judge_select", [sys.executable, "-u", "-m", "phase17.harm_judge_fix"]),
                ("harm_rejudge", [sys.executable, "-u", "-m", "phase17.harm_judge_fix", "rejudge"])],
    # Split, so the quick GPU selection runs early and the slow (possibly Gemini) re-judging last.
    "harmsel": [("harm_judge_select", [sys.executable, "-u", "-m", "phase17.harm_judge_fix"])],
    "harmre": [("harm_rejudge", [sys.executable, "-u", "-m", "phase17.harm_judge_fix", "rejudge"])],
    "phaseb1": [
        ("neutralise_own", [sys.executable, "-u", "-m", "phase17.neutralise_own"]),
        ("strong_agent_judge", [sys.executable, "-u", "-m", "phase17.neutralise_strong_agent", "judge"]),
    ],
    "phaseb": [
        ("neutralise_own", [sys.executable, "-u", "-m", "phase17.neutralise_own"]),
        ("strong_agent_judge", [sys.executable, "-u", "-m", "phase17.neutralise_strong_agent", "judge"]),
        ("ledger_radius_sweep", [sys.executable, "-u", "-m", "phase17.eval_ledger_radius_sweep"]),
    ],
}


def _kill():
    """Kill orphaned phase17 processes, sparing this runner and any pid in R7_KEEP_PIDS -- a
    remote-API job (Gemini) shares the 'phase17' command-line pattern but not the GPU."""
    if os.name == "nt":
        keep = [str(os.getpid())] + [p for p in os.environ.get("R7_KEEP_PIDS", "").split(",") if p]
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(KILL),
                        "-ExcludePid", ",".join(keep)], capture_output=True, timeout=120)


def main(names):
    LOGS.mkdir(parents=True, exist_ok=True)
    for q in names:
        for stage, cmd in QUEUES[q]:
            _kill()
            t0 = time.time()
            log = LOGS / f"r7_{stage}.log"
            print(f"[{time.strftime('%H:%M:%S')}] {stage} -> {log.name}", flush=True)
            with open(log, "w", encoding="utf-8") as fh:
                r = subprocess.run(cmd, cwd=str(ROOT), stdout=fh, stderr=subprocess.STDOUT)
            print(f"[{time.strftime('%H:%M:%S')}] {stage} exit {r.returncode} "
                  f"({time.time() - t0:.0f}s)", flush=True)
            if r.returncode != 0:
                print(f"STOPPING: {stage} failed; see {log}", flush=True)
                return r.returncode
    print("QUEUE DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["dev"]))
