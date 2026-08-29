"""Tests for the cascade invalidation engine (mvp_plan §2 core primitive).

The m1 scope covers the *algorithm*: detect a source mutation, flag the
grounded claims stale, and propagate transitively along depends_on edges.
The watchfiles watcher (m2) and the browser UI (m3) layer on top of this
tested core.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from provena.core.cascade import CascadeEngine
from provena.core.graph import ClaimDependencyGraph, ClaimStatus
from provena.core.provenance import record_claim
from provena.core.source import FileSpan


def _write_source(path: Path, body: str) -> None:
    path.write_text(dedent(body).lstrip("\n"), encoding="utf-8")


def _graph_over(path: Path) -> ClaimDependencyGraph:
    """One claim grounded on the whole file."""
    g = ClaimDependencyGraph()
    span = FileSpan.from_file(path, 1, len(path.read_text(encoding="utf-8").splitlines()))
    record_claim(g, "The file is stable.", grounded_on=[span])
    return g


# --- direct flagging -------------------------------------------------------


def test_mark_source_mutated_flags_grounded_claim(tmp_path: Path) -> None:
    src = tmp_path / "kb.py"
    _write_source(src, "def parse_config(path: str) -> dict:\n    return {}\n")
    g = _graph_over(src)
    engine = CascadeEngine(g)
    source_id = g.sources()[0].source_id

    assert engine.is_mutated(source_id) is False
    # signature refactor (same line count) mutates the span
    src.write_text("def parse_config(path: str, opts: dict) -> dict:\n    return {}\n",
                   encoding="utf-8")
    assert engine.is_mutated(source_id) is True

    flagged = engine.mark_source_mutated(source_id)
    grounded_claim = g.claims()[0]
    assert grounded_claim.id in flagged
    assert grounded_claim.status is ClaimStatus.STALE


def test_no_mutation_returns_empty(tmp_path: Path) -> None:
    src = tmp_path / "kb.py"
    _write_source(src, "def f():\n    return 1\n")
    g = _graph_over(src)
    engine = CascadeEngine(g)
    flagged = engine.mark_source_mutated(g.sources()[0].source_id)
    assert flagged == []
    assert g.claims()[0].status is ClaimStatus.FRESH


def test_unknown_source_returns_empty() -> None:
    g = ClaimDependencyGraph()
    engine = CascadeEngine(g)
    assert engine.mark_source_mutated("file:missing.py:1-1") == []


# --- transitive propagation ----------------------------------------------


def test_cascade_propagates_along_depends_on(tmp_path: Path) -> None:
    src = tmp_path / "kb.py"
    _write_source(src, "def f():\n    return 1\n")
    g = ClaimDependencyGraph()
    span = FileSpan.from_file(src, 1, 2)
    base = record_claim(g, "base grounded on file.", grounded_on=[span])
    mid = record_claim(g, "depends on base.", grounded_on=[span], depends_on=[base.id])
    top = record_claim(g, "depends on mid.", grounded_on=[span], depends_on=[mid.id])
    engine = CascadeEngine(g)

    # mutate the source
    src.write_text("def f():\n    return 2\n", encoding="utf-8")
    engine.mark_source_mutated(span.source_id)

    assert g.get_claim(base.id).status is ClaimStatus.STALE
    assert g.get_claim(mid.id).status is ClaimStatus.STALE
    assert g.get_claim(top.id).status is ClaimStatus.STALE


def test_cascade_flagging_is_idempotent(tmp_path: Path) -> None:
    src = tmp_path / "kb.py"
    _write_source(src, "def f():\n    return 1\n")
    g = ClaimDependencyGraph()
    span = FileSpan.from_file(src, 1, 2)
    base = record_claim(g, "base.", grounded_on=[span])
    record_claim(g, "derived.", grounded_on=[span], depends_on=[base.id])
    engine = CascadeEngine(g)

    src.write_text("def f():\n    return 2\n", encoding="utf-8")
    first = engine.mark_source_mutated(span.source_id)
    second = engine.mark_source_mutated(span.source_id)

    assert len(first) == 2
    # second pass: everything already stale -> no newly-flagged
    assert second == []


def test_only_mutated_subtree_is_flagged(tmp_path: Path) -> None:
    src = tmp_path / "kb.py"
    _write_source(src, "def a():\n    return 1\n\n\ndef b():\n    return 2\n")
    g = ClaimDependencyGraph()
    span_a = FileSpan.from_file(src, 1, 2)
    span_b = FileSpan.from_file(src, 5, 6)
    claim_a = record_claim(g, "a is callable.", grounded_on=[span_a])
    claim_b = record_claim(g, "b is callable.", grounded_on=[span_b])
    engine = CascadeEngine(g)

    # mutate only function a (lines 1-2); leave b untouched
    src.write_text("def a(x):\n    return 1\n\n\ndef b():\n    return 2\n", encoding="utf-8")
    engine.mark_source_mutated(span_a.source_id)

    assert g.get_claim(claim_a.id).status is ClaimStatus.STALE
    assert g.get_claim(claim_b.id).status is ClaimStatus.FRESH


def test_check_all_scans_every_source(tmp_path: Path) -> None:
    src = tmp_path / "kb.py"
    _write_source(src, "def a():\n    return 1\n\n\ndef b():\n    return 2\n")
    g = ClaimDependencyGraph()
    span_a = FileSpan.from_file(src, 1, 2)
    span_b = FileSpan.from_file(src, 5, 6)
    claim_a = record_claim(g, "a.", grounded_on=[span_a])
    claim_b = record_claim(g, "b.", grounded_on=[span_b])
    engine = CascadeEngine(g)

    # mutate both spans
    src.write_text("def a(x):\n    return 1\n\n\ndef b(y):\n    return 2\n", encoding="utf-8")
    flagged = engine.check_all()

    assert set(flagged) == {claim_a.id, claim_b.id}
    assert all(g.get_claim(c).status is ClaimStatus.STALE for c in flagged)


def test_on_flag_callback_fires_with_flagged_ids(tmp_path: Path) -> None:
    src = tmp_path / "kb.py"
    _write_source(src, "def f():\n    return 1\n")
    g = ClaimDependencyGraph()
    span = FileSpan.from_file(src, 1, 2)
    base = record_claim(g, "base.", grounded_on=[span])
    record_claim(g, "derived.", grounded_on=[span], depends_on=[base.id])

    calls: list[tuple[list[str], str]] = []

    def on_flag(claim_ids: list[str], source_id: str) -> None:
        calls.append((list(claim_ids), source_id))

    engine = CascadeEngine(g, on_flag=on_flag)
    src.write_text("def f():\n    return 2\n", encoding="utf-8")
    engine.mark_source_mutated(span.source_id)

    assert len(calls) == 1
    flagged_ids, source_id = calls[0]
    assert source_id == span.source_id
    assert set(flagged_ids) == {base.id, g.claims()[1].id}


# --- end-to-end over the toy agent ---------------------------------------


def test_toy_agent_graph_cascade_on_edit(tmp_path: Path) -> None:
    from provena.demo.agent import ToyAgent

    src = tmp_path / "source.py"
    _write_source(src, """
        def parse_config(path: str) -> dict:
            return {}

        def validate_user(user_id: str) -> bool:
            return len(user_id) > 0
    """)
    agent = ToyAgent(source_path=src)
    g = agent.run()
    engine = CascadeEngine(g)

    # every claim starts fresh
    assert all(c.status is ClaimStatus.FRESH for c in g.claims())

    # refactor parse_config's signature; the whole-file span and parse_config's
    # span both drift -> their grounded claims (and the summary dependent) flag.
    src.write_text(
        "def parse_config(path: str, opts: dict) -> dict:\n    return {}\n\n"
        "def validate_user(user_id: str) -> bool:\n    return len(user_id) > 0\n",
        encoding="utf-8",
    )
    flagged = engine.check_all()
    assert flagged  # something got flagged
    assert all(g.get_claim(c).status is ClaimStatus.STALE for c in flagged)
