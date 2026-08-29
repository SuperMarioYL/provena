"""``provena`` command-line interface.

Subcommands (mvp_plan §5):

* ``provena graph [--json]`` — print the claim-to-source DAG. **m1 done criterion.**
* ``provena trace <claim_id>`` — show the backward provenance of a claim.
* ``provena check`` — flag claims whose grounded source drifted from git HEAD.
  Uses the working tree vs. the committed baseline, so no database is needed.
* ``provena demo`` — boot the toy agent + local UI server with a live file
  watcher (the edit -> flag -> graph loop).

The CLI is a thin orchestration layer over :mod:`provena.core`,
:mod:`provena.demo`, and :mod:`provena.ui`; it owns no graph state itself.
"""

from __future__ import annotations

import json as json_lib
import subprocess
import webbrowser
from pathlib import Path
from typing import Optional

import typer

from .core.cascade import CascadeEngine
from .core.graph import ClaimStatus
from .core.provenance import trace_provenance
from .demo.agent import SOURCE_FILE, build_demo_graph

app = typer.Typer(
    name="provena",
    help="Provenance-cascade-correction for agent conclusions.",
    no_args_is_help=True,
    add_completion=False,
)


def _git_head_text(file_path: Path) -> Optional[str]:
    """Return the git-HEAD content of ``file_path`` relative to its repo, or None.

    The committed version is the natural "grounded-at-recording-time" baseline:
    it needs no database and no custom persistence (out_of_scope: in-memory only).
    Returns None outside a git repo or when the file is untracked.
    """
    file_path = Path(file_path).resolve()
    try:
        repo_root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=file_path.parent,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None
    try:
        rel = file_path.relative_to(repo_root).as_posix()
    except ValueError:
        return None
    try:
        result = subprocess.run(
            ["git", "show", f"HEAD:{rel}"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except subprocess.CalledProcessError:
        # Untracked file (no HEAD entry) — no baseline to compare against.
        return None
    return result.stdout


@app.command()
def graph(
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Emit the claim-to-source DAG as JSON (machine-readable).",
    ),
    source: Optional[Path] = typer.Option(
        None,
        "--source",
        help="Source file the toy agent grounds on (default: the bundled demo source.py).",
    ),
) -> None:
    """Print the current claim-to-source dependency graph."""
    g = build_demo_graph(source)
    if as_json:
        typer.echo(g.to_json(indent=2))
        return
    _print_graph(g)


@app.command()
def trace(
    claim_id: str = typer.Argument(..., help="The claim id to explain."),
    source: Optional[Path] = typer.Option(None, "--source", help="Demo source file."),
) -> None:
    """Show the backward provenance of a claim (its source spans + dependencies)."""
    g = build_demo_graph(source)
    if not g.has_claim(claim_id):
        typer.secho(f"unknown claim id: {claim_id}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    tr = trace_provenance(g, claim_id)
    typer.echo(f"claim  {tr.claim.id}  [{tr.claim.status.value}]")
    typer.echo(f"  text: {tr.claim.text}")
    typer.echo("  grounded_on:")
    for s in tr.grounded_sources:
        typer.echo(f"    - {s.kind:5} {s.summary()}  (hash {s.content_hash[:8]})")
    typer.echo("  depends_on:")
    for d in tr.depends_on_claims:
        typer.echo(f"    - {d.id}  [{d.status.value}]  {d.text}")


@app.command()
def check(
    source: Optional[Path] = typer.Option(None, "--source", help="Demo source file."),
) -> None:
    """Flag claims whose grounded source drifted from the committed baseline.

    Builds the graph from the *committed* (git HEAD) version of the source file,
    then re-reads each span from the working tree. Any drift flags the grounded
    claim and propagates to its dependents. Run after editing the file.
    """
    src = source or SOURCE_FILE
    baseline = _git_head_text(src)
    if baseline is None:
        typer.secho(
            "no git baseline available (not a git repo or file is untracked) — "
            "commit the source first, or run `provena demo` for live detection.",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(code=0)

    g = build_demo_graph(src, baseline_text=baseline)
    engine = CascadeEngine(g)
    flagged = engine.check_all()

    if not flagged:
        typer.secho("no stale claims — every grounded source matches the baseline.", fg=typer.colors.GREEN)
        return
    typer.secho(f"{len(flagged)} claim(s) flagged stale:", fg=typer.colors.RED)
    for cid in flagged:
        claim = g.get_claim(cid)
        typer.echo(f"  - {cid}  {claim.text}")
    typer.secho(
        "re-derive the flagged conclusions (v0.1 flags only; no auto re-derivation).",
        fg=typer.colors.YELLOW,
    )


@app.command()
def demo(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Do not open a browser."),
    no_watch: bool = typer.Option(False, "--no-watch", help="Disable the live file watcher."),
    source: Optional[Path] = typer.Option(None, "--source", help="Demo source file."),
) -> None:
    """Boot the toy agent + local UI server with the live edit -> flag loop."""
    from .ui.server import run_demo

    run_demo(
        source_path=source or SOURCE_FILE,
        host=host,
        port=port,
        open_browser=not no_browser,
        watch=not no_watch,
    )


def _print_graph(g) -> None:
    """Human-readable summary of the DAG (claims, grounding, status)."""
    if not g.claims():
        typer.echo("(empty graph)")
        return
    typer.echo(f"ClaimDependencyGraph — {len(g.claims())} claim(s), {len(g.sources())} source(s)")
    typer.echo()
    for c in g.claims():
        color = typer.colors.RED if c.status is ClaimStatus.STALE else typer.colors.CYAN
        typer.secho(f"[{c.status.value:4}] {c.id}", fg=color)
        typer.echo(f"        {c.text}")
        for s in g.grounded_sources(c.id):
            typer.echo(f"        grounded_on {s.kind:5} {s.summary()}")
        for dep in c.depends_on:
            typer.echo(f"        depends_on  {dep}")
    typer.echo()
    typer.echo(f"edges: grounded_on={len(g.to_dict()['edges']['grounded_on'])}  "
               f"depends_on={len(g.to_dict()['edges']['depends_on'])}")


def main() -> None:
    """Console-script entry point."""
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
