"""Run the mutation-proof registry from a process the orphan killer will not match.

`python -m phase17.error_registry` contains "phase17" in its command line, so a GPU queue's
pre-stage cleanup would kill it -- possibly mid-mutation, leaving a source file mutated. Run
through this wrapper the parent survives and always restores; a killed child only fails its own
entry, which is then re-run by id.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from phase17.error_registry import verify  # noqa: E402

r = verify(sys.argv[1:] or None)
print(json.dumps({k: v for k, v in r.items() if k != "errors"}))
for e in r["errors"]:
    print(e["status"], e["id"], e.get("detail", "")[:120])
