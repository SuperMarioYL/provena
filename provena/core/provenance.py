"""Provenance recording and explanation (mvp_plan §2, m1).

Two cohesive concerns live here, both about *why a claim holds*:

* :func:`record_claim` — the write protocol an agent calls when it emits a
  conclusion. It accepts ``Source`` objects (registering them) or already-known
  ``source_id`` strings, generates a stable claim id, dedupes the edge tuples,
  and hands a fully-formed :class:`Claim` to the graph. The graph owns the
  storage invariants; this module owns the recording protocol.

* :func:`trace_provenance` — the read side: a structured backward trace from a
  claim to the source spans it was grounded on and the claims it built on.
  The CLI/UI ``inspect`` feature consumes this to explain *why* a node is
  flagged.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable, Sequence

from .graph import Claim, ClaimDependencyGraph, ClaimStatus
from .source import Source


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _claim_id(text: str, source_ids: Sequence[str], dep_ids: Sequence[str]) -> str:
    """Deterministic id so re-running the toy agent yields a stable graph.

    Stability matters: the demo and tests reason about specific claim ids, and
    a real agent re-deriving the same conclusion should land on the same node
    rather than fragmenting the graph.
    """
    digest = hashlib.sha256(
        "|".join((text, *source_ids, *dep_ids)).encode("utf-8")
    ).hexdigest()[:10]
    return f"claim_{digest}"


@dataclass
class ProvenanceTrace:
    """The backward explanation of a single claim's grounding."""

    claim: Claim
    grounded_sources: list[Source]
    depends_on_claims: list[Claim]


def record_claim(
    graph: ClaimDependencyGraph,
    text: str,
    grounded_on: Iterable[Source | str],
    depends_on: Iterable[str] = (),
    *,
    claim_id: str | None = None,
) -> Claim:
    """Record an agent-emitted conclusion and wire its provenance edges.

    ``grounded_on`` accepts :class:`Source` values (registered on the fly) or
    ``source_id`` strings of sources already in the graph. ``depends_on`` is a
    list of claim ids the new conclusion builds on. Returns the stored claim.
    """
    source_ids: list[str] = []
    for entry in grounded_on:
        if isinstance(entry, str):
            if not graph.has_source(entry):
                raise KeyError(f"unknown source id: {entry!r}")
            source_ids.append(entry)
        else:
            graph.add_source(entry)
            source_ids.append(entry.source_id)

    dep_ids = tuple(dict.fromkeys(depends_on))  # dedupe, preserve order
    source_tuple = tuple(dict.fromkeys(source_ids))

    cid = claim_id or _claim_id(text, source_tuple, dep_ids)
    claim = Claim(
        id=cid,
        text=text,
        grounded_on=source_tuple,
        depends_on=dep_ids,
        status=ClaimStatus.FRESH,
        created_at=_now_iso(),
    )
    graph.add_claim(claim)
    return claim


def trace_provenance(graph: ClaimDependencyGraph, claim_id: str) -> ProvenanceTrace:
    """Build the backward provenance trace for a claim.

    Raises :class:`KeyError` if the claim is unknown. The trace is the
    one-level grounding + dependency view the inspector renders; full
    transitive reachability lives on the graph (``transitive_dependents``).
    """
    if not graph.has_claim(claim_id):
        raise KeyError(f"unknown claim id: {claim_id!r}")
    claim = graph.get_claim(claim_id)
    return ProvenanceTrace(
        claim=claim,
        grounded_sources=graph.grounded_sources(claim_id),
        depends_on_claims=[graph.get_claim(d) for d in claim.depends_on],
    )


__all__ = ["ProvenanceTrace", "record_claim", "trace_provenance"]
