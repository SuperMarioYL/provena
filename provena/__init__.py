"""Provena — provenance-cascade-correction for agent conclusions.

Provena links each agent-emitted conclusion backward to the machine-checkable
source spans it was derived from (a dataflow proxy, not a black-box rationale),
and on any source mutation cascade-flags the dependent conclusions for
re-derivation on a live claim-to-source graph.

The m1 surface exposes the data model, provenance recording, the cascade
algorithm, and a JSON-queryable graph. See :mod:`provena.cli` for the CLI.
"""

from __future__ import annotations

from .core.cascade import CascadeEngine
from .core.graph import Claim, ClaimDependencyGraph, ClaimStatus
from .core.provenance import ProvenanceTrace, record_claim, trace_provenance
from .core.source import FileSpan, ModelVersion, Source, WebUrl

__version__ = "0.1.0"

__all__ = [
    "CascadeEngine",
    "Claim",
    "ClaimDependencyGraph",
    "ClaimStatus",
    "FileSpan",
    "ModelVersion",
    "ProvenanceTrace",
    "Source",
    "WebUrl",
    "record_claim",
    "trace_provenance",
    "__version__",
]
