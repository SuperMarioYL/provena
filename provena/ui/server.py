"""FastAPI server rendering the live claim-to-source graph.

One Python process, no microservices, no DB (out_of_scope: in-memory only).
The graph is built once at startup from the toy agent's conclusions over the
demo source file, so each claim's recorded ``content_hash`` is the startup
content. A ``watchfiles`` watcher (file-span, in scope) re-reads the live file
on every save; the :class:`CascadeEngine` compares, flags, and propagates, and
the static frontend polls ``/api/graph`` to render stale nodes red.

The ``on_flag`` callback is the alert-webhook seam — a stub that logs to stdout
and an in-memory log surfaced at ``/api/flagged``. It previews the hosted team
tier (飞书/Slack alerting) without shipping a real transport (out_of_scope).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from watchfiles import awatch

from ..core.cascade import CascadeEngine
from ..core.provenance import trace_provenance
from ..demo.agent import build_demo_graph

log = logging.getLogger("provena.ui")
STATIC_DIR = Path(__file__).resolve().parent / "static"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_app(
    source_path: Path | str,
    *,
    watch: bool = True,
) -> FastAPI:
    """Build the demo app: a pre-built graph + cascade engine + optional watcher."""
    source_path = Path(source_path).resolve()
    graph = build_demo_graph(source_path)

    flag_log: list[dict] = []

    def on_flag(claim_ids: list[str], source_id: str) -> None:
        entry = {
            "at": _now_iso(),
            "source": source_id,
            "flagged": claim_ids,
            "claim_texts": [graph.get_claim(c).text for c in claim_ids],
        }
        flag_log.append(entry)
        typer_like_echo(f"[cascade] {len(claim_ids)} claim(s) flagged stale by {source_id}")
        for cid in claim_ids:
            typer_like_echo(f"  - {cid}  {graph.get_claim(cid).text}")

    engine = CascadeEngine(graph, on_flag=on_flag)

    app = FastAPI(title="Provena", version="0.1.0")
    app.state.graph = graph
    app.state.engine = engine
    app.state.source_path = str(source_path)
    app.state.flag_log = flag_log

    watcher_task: list[asyncio.Task] = []

    @app.get("/api/graph")
    def get_graph() -> dict:
        return graph.to_dict()

    @app.get("/api/trace/{claim_id}")
    def get_trace(claim_id: str) -> JSONResponse:
        if not graph.has_claim(claim_id):
            return JSONResponse({"error": f"unknown claim id: {claim_id}"}, status_code=404)
        tr = trace_provenance(graph, claim_id)
        return JSONResponse({
            "claim": {
                "id": tr.claim.id,
                "text": tr.claim.text,
                "status": tr.claim.status.value,
            },
            "grounded_sources": [
                {"source_id": s.source_id, "kind": s.kind, "summary": s.summary(),
                 "content_hash": s.content_hash}
                for s in tr.grounded_sources
            ],
            "depends_on": [{"id": d.id, "text": d.text, "status": d.status.value}
                            for d in tr.depends_on_claims],
        })

    @app.get("/api/flagged")
    def get_flagged() -> list[dict]:
        return flag_log

    @app.post("/api/check")
    def check_now() -> dict:
        flagged = engine.check_all()
        return {"flagged": flagged, "count": len(flagged)}

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @contextlib.asynccontextmanager
    async def lifespan(_app: FastAPI):
        if watch:
            task = asyncio.create_task(_watch(_app, engine, source_path))
            watcher_task.append(task)
            typer_like_echo(f"watching {source_path} for mutations (live edit -> flag)")
        typer_like_echo(f"graph ready: {len(graph.claims())} claims, "
                        f"{len(graph.sources())} sources")
        typer_like_echo("open the UI and edit the source to see cascade flags")
        try:
            yield
        finally:
            for task in watcher_task:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    app.router.lifespan_context = lifespan
    return app


async def _watch(_app: FastAPI, engine: CascadeEngine, source_path: Path) -> None:
    """Re-check every source on any change to the source file's directory.

    Filtering to the single source file keeps the watcher from reacting to
    unrelated edits; ``engine.check_all`` re-reads each span and flags only
    those whose content actually drifted since startup.
    """
    async for _changes in awatch(str(source_path)):
        try:
            engine.check_all()
        except Exception:  # pragma: no cover — watcher must not crash the server
            log.exception("cascade check failed during watch")


def run_demo(
    *,
    source_path: Path | str,
    host: str = "127.0.0.1",
    port: int = 8000,
    open_browser: bool = True,
    watch: bool = True,
) -> None:
    """Build the app and run it under uvicorn (blocking)."""
    import threading
    import webbrowser

    app = create_app(source_path, watch=watch)
    url = f"http://{host}:{port}"

    if open_browser:
        def _open() -> None:
            webbrowser.open(url)
        threading.Timer(1.0, _open).start()

    typer_like_echo(f"Provena demo — {url}")
    typer_like_echo(f"edit the source to flag dependents: {source_path}")
    config = uvicorn.Config(app, host=host, port=port, log_level="warning", lifespan="on")
    server = uvicorn.Server(config)
    server.run()


def typer_like_echo(msg: str) -> None:
    """Print without depending on typer at import time (server stays standalone)."""
    print(msg, flush=True)


__all__ = ["create_app", "run_demo"]
