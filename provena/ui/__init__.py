"""Local UI: FastAPI server + static vis-network frontend."""

from __future__ import annotations

from .server import create_app, run_demo

__all__ = ["create_app", "run_demo"]
