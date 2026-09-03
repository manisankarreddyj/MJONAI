"""FastAPI application factory for the MJONAI interactive application."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from apps.web.pages import REACT_DIST, router as pages_router
from apps.web.routes import router as api_router
from apps.web.control_routes import router as control_router
from apps.web.websocket_stream import router as websocket_router
from apps.web.research_routes import router as research_router
from apps.web.dr_routes import dr_router, health_router


def create_app() -> FastAPI:
    # Idempotent env load so ANY entrypoint (run_app.py, uvicorn CLI, tests)
    # gets credentials without depending on the launcher.
    try:
        from mjonai.core.runtime_config import load_mjonai_env

        load_mjonai_env()
    except Exception:
        pass  # views degrade to nulls honestly; /api/health stays up

    application = FastAPI(
        title="MJONAI Mission Control Terminal & API Gateway",
        version="2.0.0",
        docs_url="/api/docs",
        redoc_url=None,
    )

    application.include_router(api_router)        # /api/* (views)
    application.include_router(control_router)    # /api/v1/control/* (bidirectional commands)
    application.include_router(websocket_router)  # /ws/stream (real-time stream)
    application.include_router(research_router)   # /api/research/* (quantitative lab)
    application.include_router(dr_router)         # /api/dr/* (disaster recovery & HA)
    application.include_router(health_router)     # /api/health/* (liveness/readiness)
    application.include_router(pages_router)      # shell + manifest + sw + terminal

    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(exist_ok=True)
    application.mount(
        "/static",
        StaticFiles(directory=str(static_dir)),
        name="static",
    )

    # Mount Modern React Quantitative Cockpit
    # (frontend/ archived 2026-09-03 — mount stays dormant until a rebuilt
    #  dist/ lands at archive/frontend/dist; mount is existence-gated.
    #  REACT_DIST is shared with pages.py so render + mount agree.)
    if REACT_DIST.exists():
        react_assets = REACT_DIST / "assets"
        if react_assets.exists():
            application.mount(
                "/assets",
                StaticFiles(directory=str(react_assets)),
                name="react_assets",
            )
        application.mount(
            "/cockpit",
            StaticFiles(directory=str(REACT_DIST), html=True),
            name="react_cockpit",
        )

    @application.get("/api/health")
    def health() -> dict:
        # Deliberately facade-free liveness probe (no DB dependency).
        return {"status": "ok", "app": "mjonai-interactive", "version": "1.0.0"}

    return application


app = create_app()
