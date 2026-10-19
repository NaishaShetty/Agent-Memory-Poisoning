"""Unified benchmark: registry validation, result schema, and the fail-closed failure paths.

Runner tests use a small fake registry and fake executors, so each failure path is exercised
deterministically; `test_smoke_run_end_to_end` runs the real offline smoke subset.
"""
import copy
import json
import os

import pytest

from mambench import runner, schema, tasks
from mambench.registry import load_registry, validate_registry
from mambench.schema import SchemaError

REG = load_registry()


# --- registry ---------------------------------------------------------------------------

def test_registry_is_valid_and_every_track_has_tasks():
    validate_registry(REG)
    assert {t["track"] for t in REG["tasks"]} == set(REG["tracks"])


def test_every_executable_task_has_an_executor_and_metrics():
    for t in REG["tasks"]:
        if t.get("supported", True):
            assert callable(getattr(tasks, f"run_{t['executor']}"))
            assert t["metrics"]


@pytest.mark.parametrize("mutate, message", [
    (lambda r: r["tasks"].append(copy.deepcopy(r["tasks"][0])), "duplicated"),
    (lambda r: r["tasks"][0]["metrics"].append("no_such_metric"), "not defined"),
    (lambda r: r["tasks"][0].__setitem__("track", "no_such_track"), "unknown track"),
    (lambda r: r["tasks"][0].__setitem__("executor", "missing"), "does not exist"),
    (lambda r: r["tasks"][0].__setitem__("implementation", ["no/such/file.py"]), "not found"),
    (lambda r: r["tasks"][0].__setitem__("requires", ["gpu_cluster"]), "unknown requirement"),
    (lambda r: r["metrics"]["flag_rate"].pop("denominator"), "numerator and denominator"),
    (lambda r: r["tasks"][2].__setitem__("executor", "leakage_audit"), "must not have an executor"),
    (lambda r: r["tracks"].__setitem__("empty_track", "x"), "has no tasks"),
])
def test_registry_validation_rejects(mutate, message):
    bad = copy.deepcopy(REG)
    mutate(bad)
    with pytest.raises(SchemaError, match=message):
        validate_registry(bad)


# --- schema -----------------------------------------------------------------------------

def _result(**over):
    r = {"task_id": "integrity.leakage_audit", "task_version": "1.0", "track": "data_integrity", "status": "COMPLETED",
         "reason": "", "split_role": "not_applicable", "metrics": [schema.proportion("leakage_checks_passed", 4, 4)],
         "provenance": {k: "x" for k in schema.REQUIRED_PROVENANCE}}
    r["provenance"]["registry_version"] = REG["registry_version"]
    r.update(over)
    return r


def test_a_valid_result_passes():
    schema.validate_result(_result(), REG)


def test_zero_denominator_is_not_a_number():
    with pytest.raises(SchemaError, match="NOT_EVALUABLE"):
        schema.proportion("flag_rate", 0, 0)


@pytest.mark.parametrize("over, message", [
    ({"status": "NOT_EVALUABLE", "reason": "no data"}, "must not carry metrics"),
    ({"status": "BLOCKED", "metrics": [], "reason": ""}, "needs a reason"),
    ({"metrics": []}, "COMPLETED with no metrics"),
    ({"metrics": [schema.proportion("flag_rate", 1, 2)]}, "not declared on the task"),
    ({"metrics": [{"metric": "leakage_checks_passed", "group": None, "kind": "proportion", "numerator": 3,
                   "denominator": 4, "value": 1.0}]}, "disagrees"),
    ({"status": "PASSED_PROBABLY"}, "unknown status"),
    ({"task_id": "no.such.task"}, "not in the registry"),
])
def test_invalid_results_are_rejected(over, message):
    with pytest.raises(SchemaError, match=message):
        schema.validate_result(_result(**over), REG)


def test_missing_provenance_is_rejected():
    r = _result()
    del r["provenance"]["git_commit"]
    with pytest.raises(SchemaError, match="provenance missing"):
        schema.validate_result(r, REG)


def test_result_from_another_registry_version_is_rejected():
    r = _result()
    r["provenance"]["registry_version"] = "0.9"
    with pytest.raises(SchemaError, match="registry"):
        schema.validate_result(r, REG)


def test_aggregate_lists_unselected_tasks_as_skipped_and_has_no_overall_score():
    s = schema.aggregate([_result()], REG, ["integrity.leakage_audit"])
    assert s["n_registered_tasks"] == len(REG["tasks"]) == len(s["tasks"])
    assert s["status_counts"]["SKIPPED"] == len(REG["tasks"]) - 1
    assert "score" not in json.dumps(s).lower()


def test_aggregate_refuses_mixed_commits_and_missing_selected_results():
    a, b = _result(), _result(task_id="provenance.ledger_tamper_evidence", track="provenance_integrity",
                              metrics=[schema.proportion("tamper_detection", 4, 4)])
    b["provenance"]["git_commit"] = "other"
    with pytest.raises(SchemaError, match="different"):
        schema.aggregate([a, b], REG, [])
    with pytest.raises(SchemaError, match="produced no result"):
        schema.aggregate([a], REG, ["integrity.leakage_audit", "provenance.ledger_tamper_evidence"])


# --- runner failure paths (fake registry and executors) ---------------------------------

def _fake_registry():
    metrics = {"m": {"kind": "proportion", "numerator": "n", "denominator": "d", "direction": "context"}}
    def task(tid, executor, **kw):
        t = {"id": tid, "version": "1", "track": "t", "executor": executor, "split_role": "not_applicable",
             "requires": [], "metrics": ["m"], "implementation": [], "cost": "fast"}
        t.update(kw)
        return t
    return {"registry_version": "test", "tracks": {"t": "test"}, "metrics": metrics, "split_roles": {},
            "requirements": {"ollama": "x"}, "tasks": [
                task("ok", "fake_ok"), task("raises", "fake_raises"), task("empty", "fake_empty"),
                task("integrity", "fake_integrity"), task("mutates", "fake_mutates"),
                task("blocked", "fake_never", requires=["ollama"]),
                task("unsupported", None, supported=False, unsupported_reason="out of scope", metrics=[]),
                task("heldout", "fake_ok", split_role="frozen_holdout"),
            ]}


@pytest.fixture
def fake(monkeypatch, tmp_path):
    reg = _fake_registry()
    calls = []
    state = {"status": ""}

    def ok(params, work):
        calls.append("ok")
        return [schema.proportion("m", 1, 2)], {}

    def never(params, work):
        calls.append("never")
        raise AssertionError("a BLOCKED task must not execute")

    def raises(params, work):
        raise RuntimeError("boom")

    def empty(params, work):
        raise tasks.NotEvaluable("no evidence")

    def integrity(params, work):
        raise tasks.IntegrityViolation("digest mismatch")

    def mutates(params, work):
        state["status"] = " M phase17/data/some_result.json"
        return [schema.proportion("m", 1, 1)], {}

    for name, fn in dict(fake_ok=ok, fake_never=never, fake_raises=raises, fake_empty=empty,
                         fake_integrity=integrity, fake_mutates=mutates).items():
        monkeypatch.setattr(tasks, f"run_{name}", fn, raising=False)
    monkeypatch.setattr(runner, "load_registry", lambda: reg)
    monkeypatch.setattr(runner, "tracked_changes", lambda: state["status"])
    monkeypatch.setattr(runner, "unmet", lambda t: ["Ollama server not reachable"] if "ollama" in t["requires"] else [])
    return reg, calls, tmp_path


def _statuses(out_root):
    d = max((p for p in out_root.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime_ns)
    res = json.loads((d / "results.json").read_text(encoding="utf-8"))
    return {r["task_id"]: r for r in res["results"]}, res["summary"]


def test_each_failure_path_gets_its_own_status(fake):
    reg, calls, tmp = fake
    code = runner.run(run_all=True, out_root=tmp)
    got, summary = _statuses(tmp)
    assert {k: v["status"] for k, v in got.items()} == {
        "ok": "COMPLETED", "raises": "FAILED", "empty": "NOT_EVALUABLE", "integrity": "FAILED",
        "mutates": "FAILED", "blocked": "BLOCKED", "unsupported": "UNSUPPORTED", "heldout": "COMPLETED"}
    assert "never" not in calls  # BLOCKED and UNSUPPORTED tasks never execute
    assert "boom" in got["raises"]["reason"] and "integrity check failed" in got["integrity"]["reason"]
    assert "modified tracked files" in got["mutates"]["reason"] and got["mutates"]["metrics"] == []
    assert code == 1  # any FAILED makes the run fail
    assert sum(summary["status_counts"].values()) == len(reg["tasks"])


def test_strict_mode_fails_on_not_evaluable_and_blocked(fake):
    _, _, tmp = fake
    assert runner.run(task_ids=["ok"], out_root=tmp) == 0
    assert runner.run(task_ids=["empty"], out_root=tmp) == 0
    assert runner.run(task_ids=["empty"], out_root=tmp, strict=True) == 1
    assert runner.run(task_ids=["blocked"], out_root=tmp, strict=True) == 1


def test_repeated_holdout_evaluation_is_visible(fake):
    _, _, tmp = fake
    seen = []
    for _ in range(3):
        runner.run(task_ids=["heldout"], out_root=tmp)
        got, _ = _statuses(tmp)
        seen.append(got["heldout"]["prior_runs_of_this_split"])
    assert seen == [0, 1, 2]
    assert len([p for p in tmp.iterdir() if p.is_dir()]) == 3  # three runs, three directories, none overwritten


def test_unknown_task_or_nothing_selected_is_an_error(fake):
    _, _, tmp = fake
    with pytest.raises(SchemaError, match="unknown"):
        runner.run(task_ids=["no.such.task"], out_root=tmp)
    with pytest.raises(SchemaError, match="nothing selected"):
        runner.run(out_root=tmp)
    assert runner.main(["run", "--task", "no.such.task", "--out", str(tmp)]) == 2


# --- real tasks ---------------------------------------------------------------------------

def test_holdout_digest_task_fails_closed_on_a_mismatch(tmp_path, monkeypatch):
    import sys
    import types

    freeze = tmp_path / "f.json"
    freeze.write_text(json.dumps({"sha256": "recorded"}), encoding="utf-8")
    mod = types.ModuleType("fake_corpus")
    mod.FREEZE, mod._digest = freeze, lambda: "different"
    monkeypatch.setitem(sys.modules, "fake_corpus", mod)
    with pytest.raises(tasks.IntegrityViolation, match="MISMATCH"):
        tasks.run_holdout_freeze_digests({"modules": ["fake_corpus"]}, tmp_path)
    freeze.unlink()
    with pytest.raises(tasks.IntegrityViolation, match="freeze record missing"):
        tasks.run_holdout_freeze_digests({"modules": ["fake_corpus"]}, tmp_path)


def test_ledger_tamper_task_detects_every_mutation(tmp_path):
    metrics, details = tasks.run_ledger_tamper_evidence({}, tmp_path)
    assert all(details["detected"].values()) and len(details["detected"]) == 4


def test_smoke_run_end_to_end(tmp_path, monkeypatch):
    """The real offline smoke subset: every task COMPLETED, results valid, no tracked file touched."""
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:9")  # never call a live model from a test
    before = runner.tracked_changes()
    assert runner.run(smoke=True, out_root=tmp_path) == 0
    got, summary = _statuses(tmp_path)
    smoke = {t["id"] for t in REG["tasks"] if t.get("smoke")}
    assert set(got) == smoke
    assert all(r["status"] == "COMPLETED" for r in got.values()), {k: v["reason"] for k, v in got.items()}
    assert runner.tracked_changes() == before
