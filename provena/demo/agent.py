"""The toy scripted agent (mvp_plan §3, m1).

Not a real agent framework plugin (explicitly out of scope for v0.1). This is
a deterministic, scripted emitter: it walks ``demo/source.py`` with the AST and
records one claim per function definition, grounded on that function's source
span, plus a higher-level claim that depends on the per-function ones.

The point is to produce a *real* claim-to-source graph grounded on real spans
of a real file, so the cascade engine has something to invalidate when the file
is edited. ``record_claim`` assigns stable ids, so re-running the agent on an
unchanged file reproduces the identical graph.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from ..core.graph import ClaimDependencyGraph
from ..core.provenance import record_claim
from ..core.source import FileSpan

SOURCE_FILE = Path(__file__).resolve().parent / "source.py"


@dataclass
class ToyAgent:
    """A scripted agent that emits grounded conclusions over ``source.py``."""

    source_path: Path = SOURCE_FILE

    def run(
        self,
        graph: ClaimDependencyGraph | None = None,
        *,
        baseline_text: str | None = None,
    ) -> ClaimDependencyGraph:
        """Emit claims grounded on ``source.py`` function spans into ``graph``.

        With ``baseline_text`` unset, each span's recorded ``content_hash`` is
        the live file's current content (the happy-path demo). With
        ``baseline_text`` set (e.g. the git-HEAD version of the file), spans are
        built with :meth:`FileSpan.from_baseline`: the recorded hash is the
        baseline but :meth:`FileSpan.current_hash` still re-reads the live file,
        so ``provena check`` can detect a working-tree edit.
        """
        if graph is None:
            graph = ClaimDependencyGraph()

        text = self.source_path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(self.source_path))
        n_lines = len(text.splitlines())

        func_claims: list[str] = []
        for node in _top_level_functions(tree):
            span = _span(node.lineno, getattr(node, "end_lineno", node.lineno),
                         self.source_path, baseline_text)
            claim = record_claim(
                graph,
                text=(
                    f"`{node.name}` is defined at {span.summary()} and exposes "
                    f"a callable signature grounded on its def."
                ),
                grounded_on=[span],
            )
            func_claims.append(claim.id)

        # A higher-level conclusion that builds on the per-function claims —
        # the node that goes stale transitively when any function is refactored.
        if func_claims:
            span = _span(1, n_lines, self.source_path, baseline_text)
            record_claim(
                graph,
                text=(
                    "The module exposes a stable public surface of callables "
                    "that compose into build_profile — grounded on the whole file."
                ),
                grounded_on=[span],
                depends_on=func_claims,
            )

        return graph


def _span(start: int, end: int, path: Path, baseline_text: str | None) -> FileSpan:
    if baseline_text is not None:
        return FileSpan.from_baseline(path, start, end, baseline_text)
    return FileSpan.from_file(path, start, end)


def _top_level_functions(tree: ast.Module) -> list[ast.FunctionDef]:
    return [n for n in tree.body if isinstance(n, ast.FunctionDef)]


def build_demo_graph(
    source_path: Path | str | None = None,
    *,
    baseline_text: str | None = None,
) -> ClaimDependencyGraph:
    """Run the toy agent and return its claim-to-source graph.

    Shared by the CLI (``provena graph``) and the demo server so they reason
    about the same grounded claims. Pass ``baseline_text`` to build a graph
    whose recorded spans come from a baseline (e.g. git HEAD) while still
    pointing at the live file — used by ``provena check``.
    """
    agent = ToyAgent(source_path=Path(source_path) if source_path else SOURCE_FILE)
    return agent.run(baseline_text=baseline_text)


__all__ = ["ToyAgent", "build_demo_graph", "SOURCE_FILE"]
