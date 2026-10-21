"""Version-lockstep guard: every version surface must carry the same string.

The release version is written by hand into several independent places, so a
bump that forgets one of them ships a wheel whose surfaces disagree (e.g. a
tagged vX.Y.Z whose ``provena --version`` still reports the old version). This
test makes that drift fail mechanically on every ``pytest`` run instead of
requiring a human to read every file.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from typer.testing import CliRunner

import provena
from provena.cli import app

REPO_ROOT = Path(__file__).resolve().parent.parent

runner = CliRunner()


def _repo_version() -> str:
    return (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()


def _manifest_version() -> str:
    with (REPO_ROOT / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)["project"]["version"]


def test_version_surfaces_agree() -> None:
    surfaces = {
        "VERSION": _repo_version(),
        "pyproject.toml": _manifest_version(),
        "provena.__version__": provena.__version__,
    }
    assert len(set(surfaces.values())) == 1, f"version drift across surfaces: {surfaces}"


def test_cli_version_matches_package_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == f"provena {provena.__version__}"


def test_fastapi_app_version_matches_package_version(tmp_path: Path) -> None:
    from provena.ui.server import create_app

    src = tmp_path / "kb.py"
    src.write_text("def f():\n    return 1\n", encoding="utf-8")
    app_ = create_app(src, watch=False)
    assert app_.version == provena.__version__
