"""The ClaimDependencyGraph — the core primitive (mvp_plan §2).

A DAG whose nodes are *claims* (agent-emitted conclusions) and *sources*
(machine-checkable spans), with two edge types:

* ``grounded_on``  — claim -> source  (the claim was derived from this span).
* ``depends_on``   — claim -> claim   (one conclusion built on another).

The graph is the single source of truth for claim/source state, the edge
indices, and graph-algorithm queries (reverse adjacency, transitive closure).
It owns no business rules about *why* a claim is grounded — that lives in
:mod:`provena.core.provenance` — and no invalidation policy — that lives in
:mod:`provena.core.cascade`. This keeps storage, protocol, and invalidation
as three cohesive modules instead of one grab-bag.
"""

from __future__ import annotations

import json
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

from .source import Source


class ClaimStatus(str, Enum):
    """Lifecycle of a claim. ``fresh`` = grounded on current sources;
    ``stale`` = a grounded source (transitively) mutated and the claim is
    flagged for re-derivation. v0.1 flags only; it never auto-re-derives."""

    FRESH = "fresh"
    STALE = "stale"


@dataclass
class Claim:
    """An agent-emitted conclusion grounded on sources and/or other claims."""

    id: str
    text: str
    grounded_on: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()
    status: ClaimStatus = ClaimStatus.FRESH
    created_at: str = ""


@dataclass
class ClaimDependencyGraph:
    """In-memory claim/source DAG with both edge types and reverse indices."""

    _claims: dict[str, Claim] = field(default_factory=dict)
    _sources: dict[str, Source] = field(default_factory=dict)
    # source_id -> claims grounded on it
    _grounded_index: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    # claim_id -> claims that depend on it (reverse of depends_on)
    _dependents_index: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))

    # -- mutation ---------------------------------------------------------

    def add_source(self, source: Source) -> Source:
        """Register a source (idempotent — re-adding returns the stored copy)."""
        self._sources[source.source_id] = source
        return source

    def add_claim(self, claim: Claim) -> Claim:
        """Store a fully-formed claim and wire its edges.

        Validates that every grounded source and every dependency already lives
        in the graph, so the graph's invariants (no dangling edges) hold by
        construction. ``provenance.record_claim`` builds the value object and
        calls this; callers with a pre-built claim may use it directly.
        """
        for sid in claim.grounded_on:
            if sid not in self._sources:
                raise KeyError(f"claim {claim.id!r} grounds on unknown source {sid!r}")
        for dep in claim.depends_on:
            if dep not in self._claims:
                raise KeyError(f"claim {claim.id!r} depends on unknown claim {dep!r}")
        if claim.id in self._claims:
            raise ValueError(f"duplicate claim id: {claim.id!r}")
        self._claims[claim.id] = claim
        for sid in claim.grounded_on:
            self._grounded_index[sid].add(claim.id)
        for dep in claim.depends_on:
            self._dependents_index[dep].add(claim.id)
        return claim

    def set_status(self, claim_id: str, status: ClaimStatus) -> None:
        self._claims[claim_id].status = status

    # -- queries ----------------------------------------------------------

    def claims(self) -> list[Claim]:
        return list(self._claims.values())

    def sources(self) -> list[Source]:
        return list(self._sources.values())

    def has_source(self, source_id: str) -> bool:
        return source_id in self._sources

    def has_claim(self, claim_id: str) -> bool:
        return claim_id in self._claims

    def get_claim(self, claim_id: str) -> Claim:
        return self._claims[claim_id]

    def get_source(self, source_id: str) -> Source:
        return self._sources[source_id]

    def grounded_sources(self, claim_id: str) -> list[Source]:
        """Sources a claim was directly grounded on."""
        return [self._sources[sid] for sid in self._claims[claim_id].grounded_on]

    def claims_grounded_on(self, source_id: str) -> list[str]:
        """Claims directly grounded on a source (reverse of grounded_on)."""
        return sorted(self._grounded_index.get(source_id, set()))

    def direct_dependents(self, claim_id: str) -> list[str]:
        """Claims that directly depend_on this claim."""
        return sorted(self._dependents_index.get(claim_id, set()))

    def transitive_dependents(
        self, claim_id: str, *, include_self: bool = False
    ) -> list[str]:
        """All claims reachable from ``claim_id`` along depends_on edges.

        I.e. the forward closure: everything that breaks if this claim breaks.
        Order is BFS from the seed (deterministic for tests).
        """
        seen: set[str] = set()
        order: list[str] = []
        queue: deque[str] = deque()
        if include_self:
            queue.append(claim_id)
        else:
            queue.extend(self.direct_dependents(claim_id))
        while queue:
            cid = queue.popleft()
            if cid in seen:
                continue
            seen.add(cid)
            order.append(cid)
            queue.extend(self.direct_dependents(cid))
        return order

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> dict:
        """JSON-serialisable snapshot: nodes + both edge sets + statuses.

        This is the shape served at ``GET /api/graph`` and printed by
        ``provena graph --json``; the UI and CLI consume the same structure.
        """
        return {
            "claims": [_claim_to_dict(c) for c in self._claims.values()],
            "sources": [_source_to_dict(s) for s in self._sources.values()],
            "edges": {
                "grounded_on": [
                    {"claim": c.id, "source": sid}
                    for c in self._claims.values()
                    for sid in c.grounded_on
                ],
                "depends_on": [
                    {"from": c.id, "to": dep}
                    for c in self._claims.values()
                    for dep in c.depends_on
                ],
            },
        }

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


def _claim_to_dict(c: Claim) -> dict:
    return {
        "id": c.id,
        "text": c.text,
        "grounded_on": list(c.grounded_on),
        "depends_on": list(c.depends_on),
        "status": c.status.value,
        "created_at": c.created_at,
    }


def _source_to_dict(s: Source) -> dict:
    data = {
        "source_id": s.source_id,
        "kind": s.kind,
        "summary": s.summary(),
        "content_hash": s.content_hash,
    }
    # Surface kind-specific identity fields for the UI inspector.
    for attr in ("path", "start_line", "end_line", "model_id", "url", "fetched_at"):
        if hasattr(s, attr):
            data[attr] = getattr(s, attr)
    return data


__all__ = ["ClaimStatus", "Claim", "ClaimDependencyGraph"]
