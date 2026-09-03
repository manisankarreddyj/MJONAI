# ADR-0008: Org-level repository layout — `mjonai/` kernel namespace + apps/tools/infra

**Status:** ACCEPTED (2026-09-03, owner ruling: `mjonai/` namespace · frozen package → `tools/` · central `tests/`)
**Supersedes:** the flat `mjonai-build/` package layout as the *organizational* structure. Does NOT supersede ADR-0001 (no re-platforming — this is a move, zero behavior change) or ADR-0004 (interface minimalism).

## Context
Owner requested an organization-level codebase structure, in the pattern of how
engineering orgs actually lay out repos (namespaced monorepo: one import kernel +
deployable apps + tools + infra + decision records). The flat `mjonai-build/` tree mixed
kernel libraries, three deployables, dev tools, deploy scripts, runtime data and tests at
one level — 24 sibling directories with no ownership boundaries.

## Decision

```
MJONAI/
├── mjonai/            THE KERNEL — single import namespace; self-contained
│   ├── core/ data/ strategy/ risk/ execution/ db/ agents/
│   ├── options/ intelligence/ communication/ analytics/
│   └── research/ storage/ configs/
├── apps/              DEPLOYABLES — run them, don't import them
│   ├── runtime/       main.py + orchestration/   (the 24/7 system)
│   ├── web/           interactive PWA + API       (ADR-0007 product surface)
│   └── research/      the 7 research CLIs
├── tools/             dev/ops scripts (import anything; nothing imports them)
│   ├── mjonai_intelligence/   (FROZEN — pure move, FROZEN.md marker, content untouched)
│   └── scripts/
├── infra/             systemd unit, Oracle/Windows bootstrap, Dockerfile+compose, start_*.bat
├── tests/             central test suite (138 files; colocation per-package = future option)
├── docs/decisions/    ADR-0001…0008 (frozen decision records)
├── storage/ logs/ backups/ cache/ datasets/   runtime DATA at root (gitignored), not code
├── archive/ docs_archive/ credentials/        unchanged
└── README.md · MJONAI_DOCS.md · CLAUDE.md · audit tracker
```

**Binding dependency rules** (enforced by `tests/test_architecture_rules.py`):
1. `mjonai/*` imports only `mjonai/*`.
2. `apps/*` imports the kernel + their own files — never another app.
3. Nothing imports `tools/` or `infra/`.
4. Documented exceptions (each individually listed in the test — no blanket
   app-level exemptions):
   - `mjonai/communication/events.py` may lazy-import
     `apps/web/websocket_stream` INSIDE its existing guarded try/except (soft
     bridge — the kernel must run when the web app is absent; coupling stays
     one-directional and failure-tolerant by construction).
   - `mjonai/data/angelone/historical.py` may lazy-import
     `apps/runtime/main` INSIDE its existing guarded try/except (auto-discovers
     the attached runtime app's broker session; same soft-bridge rationale).
   - GRANDFATHERED web→runtime service edges (pre-existing under the flat
     layout, where they were plain `orchestration.*` imports):
     `apps/web/dr_routes.py` and `apps/web/websocket_stream.py` import
     `disaster_recovery`, `market_session_lifecycle` and `system_readiness`
     from `apps/runtime/orchestration/`. **Known debt**: their proper home is
     the kernel (shared services, not runtime-private); moving them is a
     refactor that needs an explicit owner ruling. The test grandfather-exacts
     exactly these two files — any NEW cross-app import fails the suite.

**Working convention change:** runtime CWD is the **repo root** (was `mjonai-build/`).
Entry points: `python apps/runtime/main.py` · `python apps/web/run_app.py` ·
`python apps/research/run_research.py` — each carries a 3-line sys.path bootstrap so
plain `python <file>` works from the root. `python -m pytest tests/` from the root.

## Alternatives rejected
- `libs/`-or-`packages/` folder style — less idiomatic for Python imports than a single
  org namespace (`mjonai.*`, matching the `shoonya.*`/`zomato.*` SDK habit the owner cited).
- Per-package test colocation — larger second change; central suite keeps the
  /engine-tests contract and minimum diff. Revisit per-package later if wanted.
- Renaming `mjonai_intelligence/` content or reopening it — anti-drift rule 3 (frozen);
  only its LOCATION changed, with a FROZEN.md marker.

## Consequences
- ~650 files moved, imports rewritten mechanically (`from core.x` → `from mjonai.core.x`);
  verified by the full runtime suite (identical pass/fail set to the pre-move baseline)
  and by the new architecture-rule test.
- `mjonai-build/` ceases to exist; Windows `D:\MJONAI\mjonai-build` paths in docs/infra
  are updated in the same session. On the owner machine this = moving the tree up one
  level; git history is preserved (git mv).
- `mjonai-build/requirements.txt` (3-line pointer) retired — the root `requirements.txt`
  (master spec sheet) + root `requirements-lock.txt` (pinned install) are the pair.
- Any new top-level directory needs an owner ruling (anti-sprawl, per ADR-0005 hygiene).
