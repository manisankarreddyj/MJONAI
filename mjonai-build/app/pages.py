"""
Server-rendered PWA pages. Stdlib string.Template only (jinja2 is NOT in the
runtime dependency set) - the shell is static; data is filled client-side by
polling the JSON API, so pages never serve stale recomputed fiction.
"""

from __future__ import annotations

from pathlib import Path
from string import Template

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

_TEMPLATES_DIR = Path(__file__).parent / "templates"


_TERMINAL_HTML = Path(__file__).parent / "static" / "terminal" / "index.html"


def _render(name: str, **substitutions: str) -> HTMLResponse:
    if _REACT_DIST.exists() and name in ("index.html", "market.html"):
        react_html = _REACT_DIST / "index.html"
        if react_html.exists():
            return HTMLResponse(react_html.read_text(encoding="utf-8"))
    html = (_TEMPLATES_DIR / name).read_text(encoding="utf-8")
    return HTMLResponse(Template(html).safe_substitute(**substitutions))


@router.get("/terminal", response_class=HTMLResponse)
def terminal_page() -> HTMLResponse:
    """Next-Gen Mission Control Terminal."""
    if _TERMINAL_HTML.exists():
        return HTMLResponse(_TERMINAL_HTML.read_text(encoding="utf-8"))
    return _render("index.html", page_title="MJONAI · Mission Control")


@router.get("/", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    # Default landing page opens the Next-Gen Mission Control Terminal if available
    if _TERMINAL_HTML.exists():
        return HTMLResponse(_TERMINAL_HTML.read_text(encoding="utf-8"))
    return _render("index.html", page_title="MJONAI")


@router.get("/trades", response_class=HTMLResponse)
def trades_page() -> HTMLResponse:
    return _render("trades.html", page_title="MJONAI · Trade history")


@router.get("/strategies", response_class=HTMLResponse)
def strategies_page() -> HTMLResponse:
    return _render("strategies.html", page_title="MJONAI · Strategy performance")


@router.get("/market", response_class=HTMLResponse)
def market_page() -> HTMLResponse:
    return _render("index.html", page_title="MJONAI · Market Cockpit")


@router.get("/install", response_class=HTMLResponse)
def install_page() -> HTMLResponse:
    return _render("install.html", page_title="MJONAI · Install on Android")


@router.get("/manifest.webmanifest")
def manifest() -> dict:
    import json

    path = Path(__file__).parent / "static" / "manifest.webmanifest"
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/sw.js", response_class=HTMLResponse)
def service_worker() -> HTMLResponse:
    js = (Path(__file__).parent / "static" / "sw.js").read_text(encoding="utf-8")
    return HTMLResponse(js, media_type="application/javascript")


@router.get("/favicon.ico")
def favicon():
    from fastapi.responses import FileResponse
    return FileResponse(Path(__file__).parent / "static" / "icon-192.png")

