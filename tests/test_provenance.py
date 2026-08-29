"""Tests for provenance recording, the graph data model, and the JSON endpoint.

Covers the m1 done criterion: claims grounded on source spans, queryable as a
graph (in Python and via the FastAPI ``/api/graph`` endpoint).
"""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pytest

from provena.core.graph import ClaimDependencyGraph, ClaimStatus
from provena.core.provenance import record_claim, trace_provenance
from provena.core.source import FileSpan, ModelVersion, WebUrl, fingerprint_text


def _write_source(path: Path, body: str) -> None:
    path.write_text(dedent(body).lstrip("\n"), encoding="utf-8")


# --- recording & edges ----------------------------------------------------


def test_record_claim_grounds_on_source(tmp_path: Path) -> None:
    src = tmp_path / "kb.py"
    _write_source(src, """
        def parse_config(path: str) -> dict:
            return {}
    """)
    g = ClaimDependencyGraph()
    span = FileSpan.from_file(src, 1, 2)
    claim = record_claim(g, "`parse_config` is a callable.", grounded_on=[span])

    assert claim.status is ClaimStatus.FRESH
    assert g.has_claim(claim.id)
    assert g.has_source(span.source_id)
    grounded = g.grounded_sources(claim.id)
    assert len(grounded) == 1 and grounded[0].source_id == span.source_id
    # reverse index: the source knows which claim grounds on it
    assert g.claims_grounded_on(span.source_id) == [claim.id]


def test_record_claim_accepts_existing_source_id(tmp_path: Path) -> None:
    src = tmp_path / "kb.py"
    _write_source(src, "def f():\n    return 1\n")
    g = ClaimDependencyGraph()
    span = FileSpan.from_file(src, 1, 2)
    g.add_source(span)
    claim = record_claim(g, "f is defined.", grounded_on=[span.source_id])
    assert g.grounded_sources(claim.id)[0].source_id == span.source_id


def test_record_claim_with_depends_on(tmp_path: Path) -> None:
    src = tmp_path / "kb.py"
    _write_source(src, "def f():\n    return 1\n")
    g = ClaimDependencyGraph()
    span = FileSpan.from_file(src, 1, 2)
    base = record_claim(g, "base conclusion.", grounded_on=[span])
    derived = record_claim(g, "derived from base.", grounded_on=[span], depends_on=[base.id])

    assert derived.depends_on == (base.id,)
    assert g.direct_dependents(base.id) == [derived.id]


def test_record_claim_rejects_unknown_source_id() -> None:
    g = ClaimDependencyGraph()
    with pytest.raises(KeyError):
        record_claim(g, "bad.", grounded_on=["file:missing.py:1-2"])


def test_record_claim_rejects_unknown_dependency(tmp_path: Path) -> None:
    src = tmp_path / "kb.py"
    _write_source(src, "def f():\n    return 1\n")
    g = ClaimDependencyGraph()
    span = FileSpan.from_file(src, 1, 2)
    with pytest.raises(KeyError):
        record_claim(g, "dangling.", grounded_on=[span], depends_on=["claim_nonexistent"])


def test_record_claim_rejects_duplicate_id(tmp_path: Path) -> None:
    src = tmp_path / "kb.py"
    _write_source(src, "def f():\n    return 1\n")
    g = ClaimDependencyGraph()
    span = FileSpan.from_file(src, 1, 2)
    record_claim(g, "first.", grounded_on=[span], claim_id="claim_x")
    with pytest.raises(ValueError):
        record_claim(g, "second.", grounded_on=[span], claim_id="claim_x")


def test_record_claim_stable_id(tmp_path: Path) -> None:
    src = tmp_path / "kb.py"
    _write_source(src, "def f():\n    return 1\n")
    span = FileSpan.from_file(src, 1, 2)
    g1 = ClaimDependencyGraph()
    g2 = ClaimDependencyGraph()
    c1 = record_claim(g1, "same conclusion.", grounded_on=[span])
    c2 = record_claim(g2, "same conclusion.", grounded_on=[span])
    assert c1.id == c2.id  # deterministic -> re-running the agent is stable


# --- trace ----------------------------------------------------------------


def test_trace_provenance(tmp_path: Path) -> None:
    src = tmp_path / "kb.py"
    _write_source(src, "def f():\n    return 1\n")
    g = ClaimDependencyGraph()
    span = FileSpan.from_file(src, 1, 2)
    base = record_claim(g, "base.", grounded_on=[span])
    derived = record_claim(g, "derived.", grounded_on=[span], depends_on=[base.id])

    tr = trace_provenance(g, derived.id)
    assert tr.claim.id == derived.id
    assert [s.source_id for s in tr.grounded_sources] == [span.source_id]
    assert [d.id for d in tr.depends_on_claims] == [base.id]


def test_trace_unknown_claim_raises() -> None:
    g = ClaimDependencyGraph()
    with pytest.raises(KeyError):
        trace_provenance(g, "claim_nope")


# --- source mutation primitives -------------------------------------------


def test_filespan_detects_edit(tmp_path: Path) -> None:
    src = tmp_path / "kb.py"
    _write_source(src, "def parse_config(path: str) -> dict:\n    return {}\n")
    span = FileSpan.from_file(src, 1, 1)
    original = span.content_hash
    assert span.current_hash() == original

    # signature refactor: same line, different content
    src.write_text("def parse_config(path: str, opts: dict) -> dict:\n    return {}\n",
                   encoding="utf-8")
    assert span.current_hash() != original


def test_model_and_web_sources_are_stubbed() -> None:
    # Out of scope for v0.1: no live model/web watcher. current_hash never drifts.
    m = ModelVersion(model_id="gpt-7b-2026")
    w = WebUrl(url="https://example.test/doc")
    assert m.current_hash() == m.content_hash == "gpt-7b-2026"
    assert w.current_hash() == w.content_hash


def test_fingerprint_text_ignores_trailing_whitespace() -> None:
    assert fingerprint_text("x = 1   \n") == fingerprint_text("x = 1\n")


# --- serialization & JSON endpoint (m1: queryable as a graph) -------------


def test_graph_to_dict_shape(tmp_path: Path) -> None:
    src = tmp_path / "kb.py"
    _write_source(src, "def f():\n    return 1\n")
    g = ClaimDependencyGraph()
    span = FileSpan.from_file(src, 1, 2)
    base = record_claim(g, "base.", grounded_on=[span])
    derived = record_claim(g, "derived.", grounded_on=[span], depends_on=[base.id])

    data = g.to_dict()
    assert len(data["claims"]) == 2
    assert len(data["sources"]) == 1
    # both claims ground on the same span -> two grounded_on edges
    assert {e["claim"] for e in data["edges"]["grounded_on"]} == {base.id, derived.id}
    assert len(data["edges"]["depends_on"]) == 1
    # round-trips through json without losing unicode
    json.loads(g.to_json())


def test_graph_json_endpoint_serves_dag(tmp_path: Path) -> None:
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from provena.ui.server import create_app

    src = tmp_path / "kb.py"
    _write_source(src, "def f():\n    return 1\n")
    app = create_app(src, watch=False)
    client = TestClient(app)

    with client:
        r = client.get("/api/graph")
        assert r.status_code == 200
        data = r.json()
        assert "claims" in data and "sources" in data and "edges" in data
        assert len(data["claims"]) >= 1
        # trace endpoint
        claim_id = data["claims"][0]["id"]
        t = client.get(f"/api/trace/{claim_id}")
        assert t.status_code == 200
        assert t.json()["claim"]["id"] == claim_id
