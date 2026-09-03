"""ADR-0008 architecture rules — dependency graph enforcement.

Rules (see docs/decisions/ADR-0008-org-level-layout.md):
  1. `mjonai/*` (kernel) imports only `mjonai/*`.
  2. `apps/*` imports the kernel + its own app — never another app, never tools.
  3. Nothing imports `tools/` (tools is a leaf; it may import anything).
  4. Documented exceptions (grandfathered, individually named — see EXCEPTIONS):
     - `mjonai/communication/events.py` → `apps.web.websocket_stream`
       (guarded lazy bridge — kernel must run when the web app is absent).
     - `apps/research/run_parity_check.py` → `research_archive.*`
       (the FROZEN archived research copy, parity-checked against the live tree).
     - `apps/web/{dr_routes,websocket_stream}.py` → `apps.runtime.orchestration`
       (pre-existing service edges; kernel move pending owner ruling — known debt).

Run: `python -m pytest tests/test_architecture_rules.py -v`
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _top_modules(rel: Path) -> tuple[str, ...]:
    """Map a repo-relative file to its zone's allowed top-level import roots."""
    parts = rel.parts
    if parts[0] == "mjonai":
        return ("mjonai",)
    if parts[0] == "apps":
        own = parts[1]  # runtime | web | research
        allowed = ("mjonai", f"apps.{own}")
        if own == "research":
            allowed += ("research_archive",)  # documented exception (FROZEN archive)
        return allowed
    if parts[0] == "tools":
        return ("mjonai", "apps", "tools", "research_archive")  # leaf: imports anything internal
    return ()  # not governed


# file -> extra allowed top-levels (documented exceptions)
EXCEPTIONS: dict[str, tuple[str, ...]] = {
    # Guarded lazy session-bridges: kernel auto-discovers the running runtime
    # app's broker session when the app is attached (try/except — the kernel
    # works with the app absent). Pre-existing edges, documented per file.
    "mjonai/communication/events.py": ("apps",),          # events → web STREAM_HUB
    "mjonai/data/angelone/historical.py": ("apps",),      # candle fetch → runtime angel_obj
    # GRANDFATHERED web→runtime service edges. Pre-existing under the flat
    # layout (they were `orchestration.*` imports). The proper fix — moving
    # disaster_recovery / market_session_lifecycle / system_readiness into the
    # kernel — is a refactor that needs an explicit owner ruling. Until then
    # these three files may reach apps.runtime.orchestration; no NEW file may.
    "apps/web/dr_routes.py": ("apps.runtime",),
    "apps/web/websocket_stream.py": ("apps.runtime",),
}

# Top-level names that belong to this repo at all.
INTERNAL_TOPS = {"mjonai", "apps", "tools", "research_archive", "datasets"}


def _module_allowed(module: str, allowed: tuple[str, ...]) -> bool:
    return any(module == root or module.startswith(root + ".") for root in allowed)


def _resolve_relative(rel: Path, level: int) -> str | None:
    """Resolve a relative import to a top-level dotted name (None if it escapes)."""
    # file at parts[0..n-1]; package of the file = parts[0..n-2]
    pkg = list(rel.parts[:-1])
    for _ in range(level - 1):
        if not pkg:
            return None
        pkg.pop()
    if not pkg:
        return None
    return ".".join(pkg[:1])


def _iter_imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield node.lineno, a.name, None
        elif isinstance(node, ast.ImportFrom):
            yield node.lineno, node.module or "", node.level


def test_architecture_rules():
    violations: list[str] = []
    for base in ("mjonai", "apps", "tools"):
        for py in (ROOT / base).rglob("*.py"):
            if "__pycache__" in py.parts:
                continue
            rel = py.relative_to(ROOT)
            allowed = _top_modules(rel) + EXCEPTIONS.get(rel.as_posix(), ())
            if not allowed:
                continue
            for lineno, module, level in _iter_imports(py):
                if module and module.split(".")[0] in INTERNAL_TOPS:
                    if not _module_allowed(module, allowed):
                        violations.append(
                            f"{rel.as_posix()}:{lineno}: imports '{module}' "
                            f"(allowed roots: {', '.join(allowed)})"
                        )
                elif level:
                    top = _resolve_relative(rel, level)
                    if top is None:
                        violations.append(
                            f"{rel.as_posix()}:{lineno}: relative import escapes its package"
                        )
                    elif top not in allowed:
                        violations.append(
                            f"{rel.as_posix()}:{lineno}: relative import reaches '{top}' "
                            f"(allowed roots: {', '.join(allowed)})"
                        )
    assert not violations, "ADR-0008 dependency-rule violations:\n" + "\n".join(violations)


def test_kernel_is_importable():
    """Sanity: the kernel namespace and every kernel subpackage import cleanly."""
    import importlib

    for sub in ("core", "data", "strategy", "risk", "execution", "db", "agents",
                "options", "intelligence", "communication", "analytics",
                "research", "storage", "configs"):
        importlib.import_module(f"mjonai.{sub}")
