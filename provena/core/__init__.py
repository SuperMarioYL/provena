"""Core primitive: the claim-to-source dependency graph and its engines."""

from __future__ import annotations

from .cascade import CascadeEngine
from .graph import Claim, ClaimDependencyGraph, ClaimStatus
from .provenance import ProvenanceTrace, record_claim, trace_provenance
from .source import FileSpan, ModelVersion, Source, WebUrl

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
]
