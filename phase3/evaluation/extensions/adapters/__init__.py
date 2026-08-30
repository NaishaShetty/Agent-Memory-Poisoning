"""Phase 3.2-H.3 -- read-only dataset adapters for the three PREPARED_CANDIDATE datasets.

Mirrors the spirit of `phase3/evaluation/integration/dataset_adapter.py` (Phase 3.2-H):
turns a candidate's own H.1-prepared normalized record (already produced, read-only, never
re-derived from `raw/` here) into a small set of typed, never-fabricating accessor calls.
Nothing in this subpackage performs any I/O beyond reading the specific candidate
`normalized/*.jsonl` / `profile/*.json` files already committed under
`phase3/datasets/candidates/<id>/` -- `raw/` is never read here.
"""
