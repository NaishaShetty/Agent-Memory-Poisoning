"""Remote-API (Gemini) queue for round 7, run OUTSIDE the GPU orphan-kill pattern.

The GPU orphan killer matches any python process whose command line contains 'phase17', because
two GPU jobs on a 6GB card stall each other. Gemini jobs are remote and do not touch the card, but
a `python -m phase17.x` command line matched the pattern and was killed twice by stage cleanup
(ROUND7_LOG R7-5). This wrapper's own command line does not match, so the serialised GPU queue and
this remote queue can run side by side, which is the only way the free tier's ~1 call/minute is
not the critical path. It never loads a local model.

    python scripts/gemini_queue.py exfil ho4mech strong
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

STEPS = {
    "exfil": lambda: [__import__("phase17.exfil_authoring", fromlist=["generate"]).generate(g)
                      for g in ("gemini_spec", "gemini_fewshot")],
    "ho4mech": lambda: __import__("phase17.holdout4_validity", fromlist=["run"]).run("mechanism"),
    "strong": lambda: __import__("phase17.neutralise_strong_agent", fromlist=["run"]).run(),
    "ho7mech": lambda: __import__("phase17.holdout7_validity", fromlist=["run"]).run("mechanism"),
    "strong120": lambda: __import__("phase17.neutralise_strong_agent", fromlist=["run"]).run(120),
    "harmstrong": lambda: __import__("phase17.harm_strong_agent", fromlist=["collect"]).collect(),
}

if __name__ == "__main__":
    for s in sys.argv[1:]:
        print(f"== {s}", flush=True)
        STEPS[s]()
        print(f"== {s} done", flush=True)
    print("GEMINI QUEUE DONE", flush=True)
