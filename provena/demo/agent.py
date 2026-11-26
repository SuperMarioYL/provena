"""The toy scripted agent (mvp_plan §3, m1).

Not a real agent framework plugin (explicitly out of scope for v0.1). This is
a deterministic, scripted emitter: it walks ``demo/source.py`` with the AST and
records one claim per function definition, grounded on that definition's source
span (decorators included), plus a higher-level claim about the module as a
whole that depends on the per-function ones.

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


class SourceUnavailableError(Exception):
    """The tracked source cannot be used: unreadable as text, or not Python.

    Raised by :meth:`ToyAgent.run` (and by the CLI's git-HEAD baseline reader)
    so the command-line boundary can report one diagnostic line and exit
    non-zero instead of leaking a raw ``FileNotFoundError`` /
    ``UnicodeDecodeError`` / ``SyntaxError`` traceback to the user.
    """


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

        if baseline_text is not None:
            # Baseline mode (provena check): the claims under check are the
            # ones recorded at baseline time, so the AST walk parses the
            # baseline — never the edited (or deleted) working tree. Otherwise
            # a removed function silently drops its claim from the check
            # instead of surfacing it as stale.
            text = baseline_text
        else:
            try:
                text = self.source_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                raise SourceUnavailableError(
                    f"cannot read source {self.source_path}: {exc}"
                ) from exc
        try:
            tree = ast.parse(text, filename=str(self.source_path))
        except SyntaxError as exc:
            raise SourceUnavailableError(
                f"source {self.source_path} is not valid Python: {exc}"
            ) from exc
        n_lines = len(text.splitlines())

        func_claims: list[str] = []
        for node in _top_level_functions(tree):
            span = _span(_definition_start(node),
                         getattr(node, "end_lineno", node.lineno),
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
        # Always recorded: a source with no top-level function still needs one
        # grounded claim, otherwise the graph is empty and `provena check`
        # reports "no stale claims" for a file where nothing was ever verified.
        # The end line is floored at 1 so an empty file stays sensitive to the
        # first line of content written into it.
        span = _span(1, max(1, n_lines), self.source_path, baseline_text)
        record_claim(
            graph,
            text="The module's public surface is grounded on the whole file.",
            grounded_on=[span],
            depends_on=func_claims,
        )

        return graph


def _definition_start(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """First line of a definition, decorators included.

    ``ast`` reports ``node.lineno`` as the ``def``/``async def`` line and gives
    each decorator its own line, so anchoring the span there silently excludes
    the decorators from the claim's evidence: a decorator-only edit (a route
    path, a cache size) would leave the claim fresh and cite a span that does
    not cover the definition.
    """
    return min([node.lineno, *(d.lineno for d in node.decorator_list)])


def _span(start: int, end: int, path: Path, baseline_text: str | None) -> FileSpan:
    if baseline_text is not None:
        return FileSpan.from_baseline(path, start, end, baseline_text)
    return FileSpan.from_file(path, start, end)


def _top_level_functions(tree: ast.Module) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    # ``async def`` parses to ast.AsyncFunctionDef, a sibling (not a subclass)
    # of ast.FunctionDef, so both must be matched or an async definition is
    # silently left ungrounded and can never be flagged stale.
    return [
        n
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


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


__all__ = ["ToyAgent", "SourceUnavailableError", "build_demo_graph", "SOURCE_FILE"]
