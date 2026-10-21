"""Tests for the CLI surface: ``--version`` and ``provena check`` exit codes.

The ``check`` tests monkeypatch ``_git_head_text`` (the git-HEAD baseline
reader) so the CLI logic is exercised without a subprocess git dependency.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from typer.testing import CliRunner

import provena
from provena.cli import app

runner = CliRunner()


def _write_source(path: Path, body: str) -> None:
    path.write_text(dedent(body).lstrip("\n"), encoding="utf-8")


def test_version_reports_package_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == f"provena {provena.__version__}"


def test_check_fail_on_stale_exit_codes(tmp_path: Path, monkeypatch) -> None:
    src = tmp_path / "kb.py"
    _write_source(src, """
        def parse_config(path: str) -> dict:
            return {}
    """)
    baseline = src.read_text(encoding="utf-8")
    monkeypatch.setattr("provena.cli._git_head_text", lambda p: baseline)

    # clean working tree -> exit 0 even with the gate on
    clean = runner.invoke(app, ["check", "--source", str(src), "--fail-on-stale"])
    assert clean.exit_code == 0
    assert "no stale claims" in clean.stdout

    # drift the span; default exit code stays 0 (demo behavior preserved)
    src.write_text(
        "def parse_config(path: str, opts: dict) -> dict:\n    return {}\n",
        encoding="utf-8",
    )
    default = runner.invoke(app, ["check", "--source", str(src)])
    assert default.exit_code == 0
    assert "flagged stale" in default.stdout

    # same drift with the gate on -> exit 1 (CI / pre-commit can rely on it)
    gated = runner.invoke(app, ["check", "--source", str(src), "--fail-on-stale"])
    assert gated.exit_code == 1
    assert "flagged stale" in gated.stdout


def test_check_survives_deleted_source_file(tmp_path: Path, monkeypatch) -> None:
    """A deleted source prints flagged claims instead of a traceback."""
    src = tmp_path / "kb.py"
    _write_source(src, "def f():\n    return 1\n")
    baseline = src.read_text(encoding="utf-8")
    monkeypatch.setattr("provena.cli._git_head_text", lambda p: baseline)

    src.unlink()

    result = runner.invoke(app, ["check", "--source", str(src), "--fail-on-stale"])
    assert result.exit_code == 1
    assert "flagged stale" in result.stdout
    assert not isinstance(result.exception, FileNotFoundError)


def test_graph_missing_source_reports_error_not_traceback(tmp_path: Path) -> None:
    """A missing --source is a clean diagnostic, not a raw FileNotFoundError."""
    missing = tmp_path / "nope.py"
    result = runner.invoke(app, ["graph", "--source", str(missing)])
    assert result.exit_code == 2
    assert not isinstance(result.exception, FileNotFoundError)
    assert "nope.py" in result.output + (result.stderr or "")


def test_trace_missing_source_reports_error_not_traceback(tmp_path: Path) -> None:
    missing = tmp_path / "nope.py"
    result = runner.invoke(app, ["trace", "claim_x", "--source", str(missing)])
    assert result.exit_code == 2
    assert not isinstance(result.exception, FileNotFoundError)


def test_graph_non_python_source_reports_error_not_traceback(tmp_path: Path) -> None:
    """A source that is not parseable as Python is a clean diagnostic too."""
    src = tmp_path / "kb.py"
    _write_source(src, "def f(:\n    return 1\n")
    result = runner.invoke(app, ["graph", "--source", str(src)])
    assert result.exit_code == 2
    assert not isinstance(result.exception, SyntaxError)
    assert "kb.py" in result.output + (result.stderr or "")


def test_check_undecodable_baseline_reports_error_not_traceback(
    tmp_path: Path, monkeypatch
) -> None:
    """An unusable git-HEAD baseline is a clean diagnostic, not a traceback."""
    from provena.demo.agent import SourceUnavailableError

    src = tmp_path / "kb.py"
    _write_source(src, "def f():\n    return 1\n")

    def _undecodable(path):
        raise SourceUnavailableError(f"cannot read {path} as UTF-8 text")

    monkeypatch.setattr("provena.cli._git_head_text", _undecodable)

    result = runner.invoke(app, ["check", "--source", str(src)])
    assert result.exit_code == 2
    assert not isinstance(result.exception, UnicodeDecodeError)
