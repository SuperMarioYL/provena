"""Source spans that agent claims are grounded on.

A ``Source`` is a machine-checkable provenance anchor — the exact place a
claim's evidence lives. Three kinds are modelled (mvp_plan §2):

* :class:`FileSpan`    — a line range in a tracked file. The only kind with a
  real mutation watcher in v0.1 (file-span is in scope; see out_of_scope).
* :class:`ModelVersion` — the identity of a model run. Stubbed interface: it
  carries a content hash but has no live watcher.
* :class:`WebUrl`       — a fetched web resource. Stubbed interface, no watcher.

Every source exposes a uniform :meth:`current_hash` used by the cascade engine
to detect mutation. For :class:`FileSpan` it re-reads the span from disk; for
the stubbed kinds it returns the recorded hash verbatim (no live detection).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import ClassVar, Protocol, runtime_checkable


def fingerprint_text(text: str) -> str:
    """Stable sha256 of ``text`` for mutation diffing.

    Line-trailing whitespace is stripped so a re-save that only changes
    trailing whitespace is not reported as a mutation.
    """
    normalised = "\n".join(line.rstrip() for line in text.splitlines())
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def fingerprint_span(text: str, start_line: int, end_line: int) -> str:
    """Fingerprint lines ``start_line..end_line`` (1-indexed) of in-memory ``text``.

    Used to compute a *baseline* hash for a span from text that is not the live
    file (e.g. the git-HEAD version), so ``check`` can compare the recorded
    baseline against the working-tree content the span points at.
    """
    lines = text.splitlines()
    start = max(0, start_line - 1)
    end = max(start, end_line)
    return fingerprint_text("\n".join(lines[start:end]))


def _read_span(path: str, start_line: int, end_line: int) -> str:
    """Read lines ``start_line..end_line`` (1-indexed, inclusive) from ``path``."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    # Lines are 1-indexed in source spans; clamp to the file bounds so an edit
    # that shrinks the file does not crash mutation detection.
    start = max(0, start_line - 1)
    end = max(start, end_line)
    return "\n".join(lines[start:end])


@runtime_checkable
class Source(Protocol):
    """Structural interface every provenance anchor implements."""

    kind: str
    source_id: str
    content_hash: str

    def summary(self) -> str: ...

    def current_hash(self) -> str: ...


@dataclass(frozen=True)
class FileSpan:
    """A line range in a tracked file — the unit of file-span provenance."""

    path: str
    start_line: int
    end_line: int
    content_hash: str
    source_id: str = ""

    kind: ClassVar[str] = "file"

    def __post_init__(self) -> None:
        if not self.source_id:
            object.__setattr__(
                self,
                "source_id",
                f"file:{self.path}:{self.start_line}-{self.end_line}",
            )

    @classmethod
    def from_file(cls, path: str | Path, start_line: int, end_line: int) -> "FileSpan":
        """Build a span by reading and fingerprinting the span's current text."""
        path = str(path)
        return cls(
            path=path,
            start_line=start_line,
            end_line=end_line,
            content_hash=fingerprint_text(_read_span(path, start_line, end_line)),
        )

    @classmethod
    def from_baseline(
        cls,
        path: str | Path,
        start_line: int,
        end_line: int,
        baseline_text: str,
    ) -> "FileSpan":
        """Build a span whose ``content_hash`` is the baseline, not the live file.

        The span still points at ``path`` (the working-tree file), so
        :meth:`current_hash` reads the live content and can diverge from the
        recorded baseline. This is how ``provena check`` detects edits without
        a database: the baseline is supplied (e.g. from git HEAD) and the
        working tree is re-read at comparison time.
        """
        return cls(
            path=str(path),
            start_line=start_line,
            end_line=end_line,
            content_hash=fingerprint_span(baseline_text, start_line, end_line),
        )

    def current_hash(self) -> str:
        """Re-fingerprint the span from disk; differs from ``content_hash`` on edit."""
        return fingerprint_text(_read_span(self.path, self.start_line, self.end_line))

    def summary(self) -> str:
        return f"{self.path}:{self.start_line}-{self.end_line}"


@dataclass(frozen=True)
class ModelVersion:
    """A model-run identity. Stubbed: no live mutation watcher."""

    model_id: str
    content_hash: str = ""
    source_id: str = ""

    kind: ClassVar[str] = "model"

    def __post_init__(self) -> None:
        if not self.source_id:
            object.__setattr__(self, "source_id", f"model:{self.model_id}")
        # A model version is immutable by definition, so its "hash" is its id.
        if not self.content_hash:
            object.__setattr__(self, "content_hash", self.model_id)

    def current_hash(self) -> str:
        # Stubbed interface (out_of_scope: model-version watcher).
        return self.content_hash

    def summary(self) -> str:
        return f"model:{self.model_id}"


@dataclass(frozen=True)
class WebUrl:
    """A fetched web resource. Stubbed: no live mutation watcher."""

    url: str
    fetched_at: str = ""
    content_hash: str = ""
    source_id: str = ""

    kind: ClassVar[str] = "web"

    def __post_init__(self) -> None:
        if not self.source_id:
            object.__setattr__(self, "source_id", f"web:{self.url}")
        if not self.fetched_at:
            object.__setattr__(self, "fetched_at", _now_iso())
        if not self.content_hash:
            object.__setattr__(self, "content_hash", self.url)

    def current_hash(self) -> str:
        # Stubbed interface (out_of_scope: web-source watcher).
        return self.content_hash

    def summary(self) -> str:
        return self.url


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
