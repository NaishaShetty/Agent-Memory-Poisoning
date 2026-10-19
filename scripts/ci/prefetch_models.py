"""Populate the Hugging Face cache with the embedding models the defences load, pinned.

    python scripts/ci/prefetch_models.py

The embedding modules set HF_HUB_OFFLINE=1 by design (phase6/defense/retrieval/
embedding_signals.py): they never fetch a model and fail loudly if it is not cached. A fresh CI
runner has an empty cache, so the models are fetched here, explicitly, and each must resolve to
the commit every reported number used. The modules load by name (the `main` ref), so `main` is
fetched and then compared with the pin; a moved `main` fails the job rather than silently
changing the model. Pins found 2026-10-18 by running the held-out split tasks against an empty
cache (exactly these two models were loaded).
"""
from __future__ import annotations

import os
import sys
import time

os.environ["HF_HUB_OFFLINE"] = "0"  # this script is the one place allowed to fetch

from huggingface_hub import snapshot_download  # noqa: E402

PINS = {
    "sentence-transformers/all-MiniLM-L6-v2": "1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
    "BAAI/bge-small-en-v1.5": "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a",
}


def main() -> int:
    for repo, pin in PINS.items():
        for attempt in range(1, 6):
            try:
                path = snapshot_download(repo, revision="main")
                break
            except Exception as exc:  # network errors: retry with backoff, then fail
                if attempt == 5:
                    print(f"FAIL: could not fetch {repo}: {exc}", file=sys.stderr)
                    return 1
                time.sleep(10 * attempt)
        resolved = os.path.basename(os.path.normpath(path))
        if resolved != pin:
            print(f"FAIL: {repo} main is now {resolved}, pinned {pin}", file=sys.stderr)
            return 1
        print(f"ok: {repo} @ {pin[:10]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
