"""
ArthAI Dashboard Backend - FastAPI Application
Main entry point for all API routes and WebSocket

API Versioning (Phase 16):
  All routes available at /api/v1/... (new standard)
  Legacy /api/... routes kept for backward compatibility
  Frontend should migrate to /api/v1/ prefix
  v2 can be added alongside v1 without breaking anything

Route map:
  /api/v1/signals        ← use this
  /api/v1/portfolio      ← use this
  /api/v1/performance    ← use this
  /api/v1/market-mood    ← use this
  /api/v1/paper-trading  ← use this
  /api/v1/assistant      ← use this
  /api/v1/watchlist      ← use this
  /api/v1/system         ← use this
  /api/v1/lessons        ← use this
  /api/v1/options        ← use this (Phase 19A)
  /api/signals           ← legacy (still works)
  /api/options           ← legacy (still works)
  ... (all legacy routes still work)
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    Depends,
    HTTPException,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from dashboard.backend.auth                    import verify_api_key, verify_ws_token
from dashboard.backend.websocket_manager       import ws_manager
from dashboard.backend.routes.signals          import router as signals_router
from dashboard.backend.routes.portfolio        import router as portfolio_router
from dashboard.backend.routes.performance      import router as performance_router
from dashboard.backend.routes.market_mood      import router as market_mood_router
from dashboard.backend.routes.paper_trading    import router as paper_trading_router
from dashboard.backend.routes.assistant        import router as assistant_router
from dashboard.backend.routes.watchlist        import router as watchlist_router
from dashboard.backend.routes.system           import router as system_router
from dashboard.backend.routes.lessons          import router as lessons_router
from dashboard.backend.routes.options          import router as options_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("ArthAI Dashboard Backend starting...")
    asyncio.create_task(ws_manager.broadcast_loop())
    yield
    logger.info("ArthAI Dashboard Backend shutting down...")


app = FastAPI(
    title       = "ArthAI Dashboard API",
    description = (
        "AI Powered Personal Trading Intelligence System\n\n"
        "**API Versioning:**\n"
        "- Current: `/api/v1/...` (use this for all new integrations)\n"
        "- Legacy: `/api/...` (backward compatible, still works)\n"
    ),
    version     = "1.0.0",
    lifespan    = lifespan,
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://*.vercel.app",
        "https://arthai.vercel.app",
    ],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)


# ── HEALTH CHECKS (No auth needed) ────────────────────────────────────────────

@app.get("/", tags=["Health"], include_in_schema=True)
async def root():
    """API root — confirms service is running."""
    return {
        "name"     : "ArthAI Dashboard API",
        "status"   : "operational",
        "version"  : "1.0.0",
        "api_v1"   : "/api/v1/",
        "docs"     : "/docs",
        "timestamp": datetime.now().isoformat(),
        "motto"    : "When in doubt, stay out",
    }


@app.get("/health", tags=["Health"], include_in_schema=True)
async def health_check():
    """Health check — used by monitoring and Kubernetes."""
    return {
        "status"   : "healthy",
        "timestamp": datetime.now().isoformat(),
        "version"  : "1.0.0",
        "services" : {
            "api"      : "up",
            "websocket": "up",
        },
    }


@app.get("/api/v1", tags=["Health"], include_in_schema=True)
async def api_v1_root():
    """API v1 root — lists all available endpoints."""
    return {
        "version"  : "v1",
        "status"   : "operational",
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "signals"      : "/api/v1/signals",
            "portfolio"    : "/api/v1/portfolio",
            "performance"  : "/api/v1/performance",
            "market_mood"  : "/api/v1/market-mood",
            "paper_trading": "/api/v1/paper-trading",
            "assistant"    : "/api/v1/assistant",
            "watchlist"    : "/api/v1/watchlist",
            "system"       : "/api/v1/system",
            "lessons"      : "/api/v1/lessons",
            "options"      : "/api/v1/options",
            "websocket"    : "/ws",
        },
        "note": (
            "All endpoints require X-API-Key header. "
            "Legacy /api/... routes still work for backward compatibility."
        ),
    }


# ── WEBSOCKET ──────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket for real-time dashboard updates.
    Client must send API key as first message.

    Message format:
      Auth     : {"api_key": "your_key"}
      Ping     : {"type": "ping"}
      Subscribe: {"type": "subscribe", "channel": "signals"}
    """
    await websocket.accept()
    client_id = None

    try:
        # Auth — first message must be API key
        auth_data = await asyncio.wait_for(
            websocket.receive_json(), timeout=10.0
        )
        api_key = auth_data.get("api_key", "")

        if not verify_ws_token(api_key):
            await websocket.send_json({
                "type"   : "error",
                "message": "Invalid API key",
            })
            await websocket.close(code=4001)
            return

        # Register connection
        client_id = await ws_manager.connect(websocket)
        logger.info(f"WebSocket client connected: {client_id}")

        await websocket.send_json({
            "type"     : "connected",
            "client_id": client_id,
            "message"  : "ArthAI Dashboard connected",
            "timestamp": datetime.now().isoformat(),
        })

        # Listen for client messages
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_json(), timeout=30.0
                )

                if data.get("type") == "ping":
                    await websocket.send_json({
                        "type"     : "pong",
                        "timestamp": datetime.now().isoformat(),
                    })

                elif data.get("type") == "subscribe":
                    channel = data.get("channel", "all")
                    ws_manager.subscribe(client_id, channel)
                    await websocket.send_json({
                        "type"   : "subscribed",
                        "channel": channel,
                    })

            except asyncio.TimeoutError:
                # Heartbeat to keep connection alive
                await websocket.send_json({
                    "type"     : "heartbeat",
                    "timestamp": datetime.now().isoformat(),
                })

    except WebSocketDisconnect:
        if client_id:
            ws_manager.disconnect(client_id)
            logger.info(f"WebSocket client disconnected: {client_id}")
    except asyncio.TimeoutError:
        logger.warning("WebSocket auth timeout")
        await websocket.close(code=4002)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if client_id:
            try:
                ws_manager.disconnect(client_id)
            except Exception:
                pass


# ── API v1 ROUTES — PRIMARY (Phase 16) ────────────────────────────────────────
# All new integrations use /api/v1/ prefix.
# Version is in the URL — v2 can be added without breaking v1 callers.

_AUTH = [Depends(verify_api_key)]

app.include_router(
    signals_router,
    prefix       = "/api/v1/signals",
    tags         = ["v1 — Signals"],
    dependencies = _AUTH,
)

app.include_router(
    portfolio_router,
    prefix       = "/api/v1/portfolio",
    tags         = ["v1 — Portfolio"],
    dependencies = _AUTH,
)

app.include_router(
    performance_router,
    prefix       = "/api/v1/performance",
    tags         = ["v1 — Performance"],
    dependencies = _AUTH,
)

app.include_router(
    market_mood_router,
    prefix       = "/api/v1/market-mood",
    tags         = ["v1 — Market Mood"],
    dependencies = _AUTH,
)

app.include_router(
    paper_trading_router,
    prefix       = "/api/v1/paper-trading",
    tags         = ["v1 — Paper Trading"],
    dependencies = _AUTH,
)

app.include_router(
    assistant_router,
    prefix       = "/api/v1/assistant",
    tags         = ["v1 — Assistant"],
    dependencies = _AUTH,
)

app.include_router(
    watchlist_router,
    prefix       = "/api/v1/watchlist",
    tags         = ["v1 — Watchlist"],
    dependencies = _AUTH,
)

app.include_router(
    system_router,
    prefix       = "/api/v1/system",
    tags         = ["v1 — System"],
    dependencies = _AUTH,
)

app.include_router(
    lessons_router,
    prefix       = "/api/v1/lessons",
    tags         = ["v1 — Lessons"],
    dependencies = _AUTH,
)

app.include_router(
    options_router,
    prefix       = "/api/v1/options",
    tags         = ["v1 — Options"],
    dependencies = _AUTH,
)


# ── LEGACY ROUTES — BACKWARD COMPATIBLE ───────────────────────────────────────
# These /api/... routes continue to work.
# Frontend can migrate to /api/v1/ at its own pace.
# Do NOT remove these until frontend is fully migrated.

app.include_router(
    signals_router,
    prefix            = "/api/signals",
    tags              = ["Legacy — Signals"],
    dependencies      = _AUTH,
    include_in_schema = False,
)

app.include_router(
    portfolio_router,
    prefix            = "/api/portfolio",
    tags              = ["Legacy — Portfolio"],
    dependencies      = _AUTH,
    include_in_schema = False,
)

app.include_router(
    performance_router,
    prefix            = "/api/performance",
    tags              = ["Legacy — Performance"],
    dependencies      = _AUTH,
    include_in_schema = False,
)

app.include_router(
    market_mood_router,
    prefix            = "/api/market-mood",
    tags              = ["Legacy — Market Mood"],
    dependencies      = _AUTH,
    include_in_schema = False,
)

app.include_router(
    paper_trading_router,
    prefix            = "/api/paper-trading",
    tags              = ["Legacy — Paper Trading"],
    dependencies      = _AUTH,
    include_in_schema = False,
)

app.include_router(
    assistant_router,
    prefix            = "/api/assistant",
    tags              = ["Legacy — Assistant"],
    dependencies      = _AUTH,
    include_in_schema = False,
)

app.include_router(
    watchlist_router,
    prefix            = "/api/watchlist",
    tags              = ["Legacy — Watchlist"],
    dependencies      = _AUTH,
    include_in_schema = False,
)

app.include_router(
    system_router,
    prefix            = "/api/system",
    tags              = ["Legacy — System"],
    dependencies      = _AUTH,
    include_in_schema = False,
)

app.include_router(
    lessons_router,
    prefix            = "/api/lessons",
    tags              = ["Legacy — Lessons"],
    dependencies      = _AUTH,
    include_in_schema = False,
)

app.include_router(
    options_router,
    prefix            = "/api/options",
    tags              = ["Legacy — Options"],
    dependencies      = _AUTH,
    include_in_schema = False,
)


# ── ERROR HANDLERS ─────────────────────────────────────────────────────────────

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code = exc.status_code,
        content     = {
            "error"      : exc.detail,
            "status_code": exc.status_code,
            "timestamp"  : datetime.now().isoformat(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code = 500,
        content     = {
            "error"      : "Internal server error",
            "status_code": 500,
            "timestamp"  : datetime.now().isoformat(),
        },
    )