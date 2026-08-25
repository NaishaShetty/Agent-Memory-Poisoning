from __future__ import annotations

from preprocessing.io_utils import deterministic_id, iter_jsonl, sha256_file, write_jsonl


def test_deterministic_id_is_stable_and_order_sensitive():
    a = deterministic_id("dataset", "file", "conv1", "session1", "turn1")
    b = deterministic_id("dataset", "file", "conv1", "session1", "turn1")
    c = deterministic_id("dataset", "file", "conv1", "session1", "turn2")
    assert a == b
    assert a != c


def test_deterministic_id_distinguishes_field_boundaries():
    # "ab"+"c" vs "a"+"bc" must not collide just because concatenation matches
    a = deterministic_id("ab", "c")
    b = deterministic_id("a", "bc")
    assert a != b


def test_sha256_file_matches_known_content(tmp_path):
    p = tmp_path / "f.txt"
    p.write_text("hello world", encoding="utf-8")
    import hashlib

    expected = hashlib.sha256(b"hello world").hexdigest()
    assert sha256_file(p) == expected


def test_jsonl_roundtrip(tmp_path):
    p = tmp_path / "out.jsonl"
    records = [{"a": 1}, {"a": 2}]
    n = write_jsonl(p, records)
    assert n == 2
    assert list(iter_jsonl(p)) == records


def test_iter_jsonl_raises_on_malformed_line(tmp_path):
    p = tmp_path / "bad.jsonl"
    p.write_text('{"a": 1}\nnot json\n', encoding="utf-8")
    import pytest

    with pytest.raises(ValueError, match="Malformed JSONL"):
        list(iter_jsonl(p))


def test_iter_jsonl_skips_blank_lines(tmp_path):
    p = tmp_path / "blank.jsonl"
    p.write_text('{"a": 1}\n\n\n{"a": 2}\n', encoding="utf-8")
    assert list(iter_jsonl(p)) == [{"a": 1}, {"a": 2}]
