"""Test isolation for v7: `common.isolate()` (also run when g1_v7 / g2_v7 / g3_v7 are imported) re-points module-level cache
paths of v3/v4/v6 modules to v7 files. In a shared pytest session that change would leak into the v6 tests, which check
those same attributes. This fixture snapshots the attributes before every v7 test and restores them afterwards."""
from __future__ import annotations

import pytest

_ATTRS = [("phase17.defence_v3.vpl", "CACHE"), ("phase17.defence_v4.voa", "PARTIAL"), ("phase17.defence_v6.fpb", "NLI_CACHE"),
          ("phase17.defence_v6.g1_eval", "DEC_CACHE"), ("phase17.defence_v6.g1_eval", "SEL"), ("phase17.defence_v6.g1_eval", "OUT"),
          ("phase17.defence_v6.g3_eval", "SIG"), ("phase17.defence_v6.g3_eval", "SELK"), ("phase17.defence_v6.g3_eval", "OUT")]


def _snapshot():
    import importlib

    mods = {mod: importlib.import_module(mod) for mod, _ in _ATTRS}   # import ALL first: g3_eval sets voa.PARTIAL on import
    return [(mods[mod], attr, getattr(mods[mod], attr)) for mod, attr in _ATTRS]


_ORIGINAL = _snapshot()          # taken when this conftest is collected, before any v7 module is imported


@pytest.fixture(autouse=True)
def _restore_v6_module_state():
    yield
    for m, attr, v in _ORIGINAL:
        setattr(m, attr, v)
