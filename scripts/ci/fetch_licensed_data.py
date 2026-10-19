"""Fetch the licensed raw data the hosted CI needs, pinned and digest-verified.

    python scripts/ci/fetch_licensed_data.py

Only LoCoMo is fetched: it is what the leakage audit and the held-out split evaluations need,
and its licence (CC BY-NC 4.0) allows non-commercial use with attribution. It is downloaded at
run time and never committed (data/raw/ is gitignored), so nothing is redistributed. MSC has no
explicit dataset licence and is never fetched.

Each file is downloaded from a pinned upstream commit and must match the sha256 recorded in
data/metadata/dataset_manifest.json (the digest of the copy every reported number used);
anything else fails the job. An existing file is kept only if it matches. The pinned commits
were matched to the manifest on 2026-10-18 (identical git blob hashes, then sha256).
"""
from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "data" / "metadata" / "dataset_manifest.json"
UPSTREAM = "https://raw.githubusercontent.com/snap-research/locomo"
FILES = {  # repository path -> (upstream commit, upstream path)
    "data/raw/locomo/locomo10.json": ("cbfbc1dba6bc53d00625212a0f22d55ffee7c1fc", "data/locomo10.json"),
    "data/raw/locomo/LICENSE.txt": ("a9f0a462c37e3c2e5285aec393e0598e03fc9e4d", "LICENSE.txt"),
}


def _expected() -> dict:
    files = json.loads(MANIFEST.read_text(encoding="utf-8"))["datasets"]["locomo"]["files"]
    return {f["path"].replace("\\", "/"): f["sha256"] for f in files}


def main() -> int:
    expected = _expected()
    for rel, (commit, upstream_path) in FILES.items():
        want = expected[rel]
        dest = ROOT / rel
        if dest.is_file():
            got = hashlib.sha256(dest.read_bytes()).hexdigest()
            if got != want:
                print(f"FAIL: {rel} exists with sha256 {got}, manifest says {want}", file=sys.stderr)
                return 1
            print(f"ok (present): {rel}")
            continue
        url = f"{UPSTREAM}/{commit}/{upstream_path}"
        with urllib.request.urlopen(url, timeout=120) as r:
            data = r.read()
        got = hashlib.sha256(data).hexdigest()
        if got != want:
            print(f"FAIL: {url} has sha256 {got}, manifest says {want}", file=sys.stderr)
            return 1
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        print(f"ok (fetched, verified): {rel} from {commit[:10]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
