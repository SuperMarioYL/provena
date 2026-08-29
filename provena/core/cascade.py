"""Cascade invalidation engine (mvp_plan §2, m1 logic / m2 watcher hook).

The genuinely-new structure: the unit of invalidation is an *agent's emitted
conclusion*, not a file or a code-graph node. When a source a claim was grounded
on mutates, the engine flags the directly-grounded claims ``stale`` and
propagates ``stale`` transitively along ``depends_on`` edges — Bazel-style
dirty-marking lifted from code-graph nodes to agent-claim nodes.

Scope split (mvp_plan §5):

* **m1** (this module): the invalidation *algorithm* — detect mutation via
  :meth:`Source.current_hash`, flag, propagate. Pure and tested.
* **m2**: a ``watchfiles`` watcher that calls :meth:`mark_source_mutated` when a
  tracked file changes. Not implemented here; ``provena demo`` wires it.

v0.1 only *flags* for re-derivation; it never auto-re-derives (out_of_scope).
"""

from __future__ import annotations

from collections import deque
from typing import Callable, Iterable

from .graph import ClaimDependencyGraph, ClaimStatus
from .source import Source

# A flag callback receives (newly_flagged_claim_ids, source_id). The demo uses
# it as the alert-webhook seam — a stub previewing the hosted team tier
# (飞书/Slack alerting). It is intentionally optional so the core has no
# dependency on any transport.
FlagCallback = Callable[[list[str], str], None]


class CascadeEngine:
    """Detect source mutations and propagate ``stale`` over the claim DAG."""

    def __init__(
        self,
        graph: ClaimDependencyGraph,
        on_flag: FlagCallback | None = None,
    ) -> None:
        self._graph = graph
        self._on_flag = on_flag

    def is_mutated(self, source_id: str) -> bool:
        """True if the source's current content differs from recording time."""
        source = self._graph.get_source(source_id)
        return source.current_hash() != source.content_hash

    def mutated_sources(self) -> list[str]:
        """All known sources whose content has drifted since recording."""
        return [s.source_id for s in self._graph.sources() if self.is_mutated(s.source_id)]

    def mark_source_mutated(self, source_id: str) -> list[str]:
        """Flag claims grounded on a mutated source, then propagate.

        Returns the ids of all claims that transitioned fresh -> stale in this
        pass (the directly-grounded claims plus their transitive dependents),
        in dependency order. If the source is not actually mutated, returns
        ``[]`` and changes nothing.
        """
        if not self._graph.has_source(source_id):
            return []
        if not self.is_mutated(source_id):
            return []

        flagged: list[str] = []
        # Seed: every claim directly grounded on the mutated source.
        seeds = self._graph.claims_grounded_on(source_id)
        for seed in seeds:
            flagged.extend(self._flag_subtree(seed))

        # Dedupe preserving dependency order.
        flagged = list(dict.fromkeys(flagged))
        if flagged and self._on_flag:
            self._on_flag(flagged, source_id)
        return flagged

    def check_all(self) -> list[str]:
        """Run mutation detection across every source; return flagged claim ids."""
        flagged: list[str] = []
        for source in self._graph.sources():
            flagged.extend(self.mark_source_mutated(source.source_id))
        return list(dict.fromkeys(flagged))

    def _flag_subtree(self, claim_id: str) -> list[str]:
        """Mark ``claim_id`` and its transitive dependents stale (BFS).

        Already-stale nodes are skipped (idempotent re-flagging) but still
        traversed so dependents reachable through them are reached.
        """
        out: list[str] = []
        seen: set[str] = set()
        queue: deque[str] = deque([claim_id])
        while queue:
            cid = queue.popleft()
            if cid in seen:
                continue
            seen.add(cid)
            claim = self._graph.get_claim(cid)
            if claim.status is not ClaimStatus.STALE:
                self._graph.set_status(cid, ClaimStatus.STALE)
                out.append(cid)
            queue.extend(self._graph.direct_dependents(cid))
        return out


__all__ = ["CascadeEngine", "FlagCallback"]
