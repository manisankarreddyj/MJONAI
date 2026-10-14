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
  5. Strategy-source boundary (anti-drift rule 4): `strategy/registry/` is the
     ONLY place a `BaseStrategy` subclass may be defined, and
     `mjonai.research.discovery` is research-tier only (never apps/runtime,
     apps/web, or a non-research kernel module).

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


# ---------------------------------------------------------------------------
# Strategy-source boundary
#
# Anti-drift rule: `strategy/registry/` is the ONLY strategy codebase. The
# research tier must never grow a second, parallel source of trading logic, and
# research-only primitives must never reach production.
#
# This matters concretely: `mjonai/research/discovery/signals.py` (recovered
# 2026-10-04, from an unrecorded 2026-09-27 session) registers 7 signal
# families whose ideas overlap the registry (A2 sig_donchian ~ S03
# TurtleBreakout, A1 time-series momentum ~ S01/S16). Those are NOT duplicate
# strategy implementations -- they are bare vectorized hypothesis primitives
# (`fn(df, params) -> Series` of target positions) with no scoring, stops,
# regime gate, or evidence layer, one architectural layer below a
# BaseStrategy. Overlapping IDEAS are legitimate in a discovery harness; what
# is not legitimate is a second tradable strategy, or a research primitive
# being promoted into the live path without registry review. Both are pinned
# below.
# ---------------------------------------------------------------------------

_STRATEGY_SUBCLASS_MARKERS = ("BaseStrategy",)


def _subclasses_base_strategy(path: Path) -> list[str]:
    """Return names of classes in `path` that subclass BaseStrategy."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            name = ""
            if isinstance(base, ast.Name):
                name = base.id
            elif isinstance(base, ast.Attribute):
                name = base.attr
            elif isinstance(base, ast.Call):  # e.g. BaseStrategy(x)
                fn = base.func
                name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", "")
            if any(marker in name for marker in _STRATEGY_SUBCLASS_MARKERS):
                hits.append(node.name)
    return hits


def test_strategy_registry_is_the_only_strategy_source():
    """No BaseStrategy subclass may be defined outside strategy/registry/.

    This is the anti-drift rule made mechanical: research CLIs, harnesses, and
    helper modules may not quietly accumulate tradable strategies alongside the
    registry. A new strategy goes in strategy/registry/ and nowhere else.
    """
    violations: list[str] = []
    for py in (ROOT / "mjonai").rglob("*.py"):
        if "__pycache__" in py.parts:
            continue
        rel = py.relative_to(ROOT).as_posix()
        for cls in _subclasses_base_strategy(py):
            if not rel.startswith("mjonai/strategy/registry/"):
                violations.append(f"{rel}: class {cls} subclasses BaseStrategy")
    assert not violations, (
        "strategy/registry/ must remain the only strategy codebase "
        "(anti-drift rule 4):\n" + "\n".join(violations)
    )


def test_open_trades_reads_are_mode_scoped():
    """Every open-book read must filter by system_mode — an unscoped
    get_open_trades() mixes RESEARCH rows into PAPER/LIVE monitoring, views,
    position limits, and Telegram commands (P0 fix 2026-10-14).

    Allowed exception: execution/orders.py close_paper_trade's by-ID lookup
    (the UUID disambiguates; scoping it could strand cross-mode closes).
    """
    offenders: list[str] = []
    for base in (ROOT / "mjonai", ROOT / "apps"):
        for py in base.rglob("*.py"):
            if "__pycache__" in py.parts:
                continue
            rel = py.relative_to(ROOT).as_posix()
            try:
                tree = ast.parse(py.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):
                continue
            # AST sees real calls only — comments and docstrings are invisible
            # by construction, so prose mentioning get_open_trades() is fine.
            # Track enclosing function per node via a parent walk.
            parents: dict = {}
            for node in ast.walk(tree):
                for child in ast.iter_child_nodes(node):
                    parents[child] = node
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                        and node.func.id == "get_open_trades"):
                    continue
                if any(kw.arg == "system_mode" for kw in node.keywords):
                    continue
                enclosing = ""
                probe = node
                while probe in parents:
                    probe = parents[probe]
                    if isinstance(probe, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        enclosing = probe.name
                        break
                if rel == "mjonai/execution/orders.py" and enclosing == "close_paper_trade":
                    continue  # by-ID lookup: UUID disambiguates modes
                offenders.append(f"{rel}:{node.lineno}: unscoped get_open_trades() in {enclosing or '?'}()")
    assert not offenders, (
        "open-book reads must pass system_mode=...:\n" + "\n".join(offenders)
    )


def test_research_discovery_never_reaches_production():
    """`mjonai.research.discovery` is research-tier only.

    Allowed consumers: the research CLIs under `apps/research/` and the
    research suite. Forbidden: the live engine (apps/runtime), the web app
    (apps/web), and any kernel module outside `mjonai/research/`. This keeps a
    discovery primitive from being promoted into the trading path without
    passing registry review.
    """
    violations: list[str] = []
    candidates: list[Path] = []
    for py in (ROOT / "mjonai").rglob("*.py"):
        rel = py.relative_to(ROOT).as_posix()
        if "__pycache__" in py.parts or rel.startswith("mjonai/research/"):
            continue
        candidates.append(py)
    for base in ("apps/runtime", "apps/web"):
        candidates.extend(p for p in (ROOT / base).rglob("*.py") if "__pycache__" not in p.parts)

    for py in candidates:
        rel = py.relative_to(ROOT).as_posix()
        for lineno, module, _level in _iter_imports(py):
            if module.startswith("mjonai.research.discovery"):
                violations.append(f"{rel}:{lineno}: imports '{module}'")
    assert not violations, (
        "research/discovery must not be imported by production code:\n"
        + "\n".join(violations)
    )


def test_discovery_signals_are_research_primitives_not_strategies():
    """The discovery signal families must stay bare vectorized primitives.

    Each family is `fn(df, params) -> pd.Series` of target positions. They must
    not subclass BaseStrategy (pinned above) and must not import the registry,
    so the registry stays the single owner of tradable strategy logic.
    """
    signals = ROOT / "mjonai" / "research" / "discovery" / "signals.py"
    assert signals.exists(), "discovery/signals.py missing"
    offenders = [
        f"{module}"
        for _lineno, module, _level in _iter_imports(signals)
        if "strategy.registry" in module
    ]
    assert not offenders, (
        "discovery/signals.py must not import the strategy registry -- a "
        f"research primitive may not depend on tradable strategy logic: {offenders}"
    )
