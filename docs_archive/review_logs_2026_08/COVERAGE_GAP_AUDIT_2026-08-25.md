# MJONAI COVERAGE-GAP AUDIT — 2026-08-25 (second pass)

**Relationship to first pass:** builds on `FULL_SYSTEM_FORENSIC_AUDIT_2026-08-25.md` without repeating it. Purpose: prove what the first audit actually covered, close cheap read-gaps, extend ecosystem research, verify the AI-dev chain end-to-end, and register everything that remains unknown.

**Constraints honored:** zero modifications to the project, config, MCP, memory, or Git state. All work read-only except this report file. (Per instruction, auto-memory was NOT written this turn.)

---

## 1. DEFINITIVE INVENTORY (filesystem vs git)

### 1.1 Raw counts (verified by enumeration, 2026-08-25)

| Scope | Files | Dirs | Notes |
|---|---|---|---|
| **D:\MJONAI total** | **18,606** | **2,113** | includes .venv and .git objects |
| `.venv\` (Python 3.11.9 env) | 17,359 | ~2,000 | GENERATED; shared runtime; 92 installed distributions (`pip list`) |
| `.git\` (mjonai-build) | packed: 85.89 MiB size-pack, 123 loose objects | — | remote: `github.com/manisankarreddyj/mjonai-build.git`; **17 local commits unpushed** |
| **mjonai-build\** (excl. .git) | **1,110** | ~120 | the only version-controlled tree |
| ↳ git-tracked | **513** | | |
| ↳ untracked-not-ignored | **2** | | `migrate_minute_cache.py`, `research/sector_scanner.py` (both previously adjudicated) |
| ↳ ignored entries | 39 paths | | `__pycache__` dirs, `logs/`, `scratch/*.log`, `storage/parquet/**`, datasets placeholders |
| mjonai-dashboard\ | 48 | ~15 | SUPERSEDED stack (ADR-0007); includes stale `__pycache__` |
| docs_archive\ | 49 | ~10 | evidence ledgers + historical docs |
| planning\ | 11 | 1 | working drafts + ADR-0001..0007 |
| credentials\ | 1 | 0 | `.env.master` (never opened) |
| scripts\ | 3 | 0 | systemd unit, Oracle VM setup, Windows setup |
| root files | 8 | | AGENTS.md, CLAUDE.md, MJONAI_DOCS.md, BLUEPRINT, README.md, create_full_snapshot.ps1, pyrightconfig.json, requirements.txt |
| .claude\ | 6 | | settings.json, settings.local.json, launch.json, hooks/block_secrets.py, skills/engine-tests/SKILL.md, agents/test-worker.md |
| .codex\ | 4 | | config.toml, hooks.json, hooks/block_secrets.py (byte-identical to .claude's — diff-verified), agents/test-worker.toml |
| .agents\ | 1 | | skills/engine-tests/SKILL.md |
| .vscode\ | 1 | | settings.json |
| .pytest_cache\ (×2 levels) | 5 | | generated |

**Notebooks: zero. Docker/Compose: zero. CI (.github etc.): zero. Other DBs: one** (`research_archive/research_data.duckdb`, 91.3MB, tracked). Binaries outside .venv: none beyond app icons (`app/static/*.png`). Extension histogram dominated by venv artifacts (pyc/pyd/h/lib); project source ≈ **6847 py total minus venv ⇒ ~700 project .py files incl. archives/tests**, 95 md.

### 1.2 Reconciliation verdict

Filesystem ⇄ Git inventories reconcile cleanly: every non-venv, non-cache artifact is either tracked (513), one of 2 known untracked files, or inside the documented ignored globs. **No orphan or surprise artifact classes were found.** The two structural anomalies worth stating:

- **K-A1 (NEW, HIGH — knowledge layer is NOT version-controlled):** only `mjonai-build/` is a git repo. `MJONAI_DOCS.md`, `CLAUDE.md`, `planning/**` (all seven ADRs), `docs_archive/**` (every evidence ledger incl. both audits), `scripts/**`, root `requirements.txt`, and the blueprint live **outside any repository**. A disk failure loses the entire authoritative memory of the project while sparing its code. `create_full_snapshot.ps1` was inspected: it generates a **text snapshot for AI context** (secret-aware exclusions) — it is *not* a backup mechanism. This is the largest single portability risk found across both passes. Resolution requires an owner decision (e.g., make D:\MJONAI a repo, or move docs into mjonai-build) — recorded, not executed.
- Scratch/journals/instrument-cache are git-tracked *inside* mjonai-build (permanent `' M'` churn, 91MB duckdb history bloat) — inverse problem, already flagged pass 1 (§12/§13).

---

## 2. DOT-DIRECTORY VERIFICATION (deep)

| Dir | Contents (verified) | Secrets? | Memory? | Hooks? | MCP? | Agents/skills? | Version-control it? |
|---|---|---|---|---|---|---|---|
| `D:\MJONAI\.claude\` | settings.json (model pins ×3 → ox-alpha; PreToolUse secret hook), settings.local.json (**accumulated permission grants incl. broad `Bash(git add *)`, `PowerShell(Set-Content *)` — drifts vs CLAUDE.md staging rule**), launch.json (preview server `mjonai-app` :8787), hooks/block_secrets.py, skills/engine-tests, agents/test-worker.md | No | No | Yes | **None configured** | Yes | Project-local; safe to track (no secrets found); currently untracked because parent isn't a repo |
| `C:\Users\manis\.claude\` | settings.json = `{"enableWorkflows": true}` ONLY; no global CLAUDE.md; **no plugins, no commands, no agents, no scheduled tasks**; projects\D--MJONAI\ holds session transcripts (jsonl) + `memory\` (auto-memory: MEMORY.md index + engagement + openrouter-credits notes) | No | **Yes — AI-side convenience memory lives here** (non-authoritative per ADR-0005) | No | None | None | Local-only by design; disposable under ADR-0005 hierarchy |
| `.codex\` | config.toml (same three model pins via shell_environment_policy), hooks.json + identical secret hook, test-worker.toml | No | No | Yes | None | test-worker agent | Same status as .claude |
| `.agents\` | engine-tests SKILL.md mirror | No | No | No | No | Yes | same |
| `.vscode\` | interpreter → root .venv; extraPaths workspace+build; pytest args `mjonai-build/tests` | No | No | No | No | No | fine |
| `.pytest_cache\` (root + build) | lastfailed/nodeids caches | No | No | No | No | No | ignored/generated |
| `.git\` (mjonai-build) | standard; no custom hooks (sample hooks only — checked listing pattern); fsck not run (time) | n/a | n/a | none active | n/a | n/a | is the VC |

Chain conclusion (§7 detail): gateway/model routing is defined by **machine-level environment variables** (`ANTHROPIC_BASE_URL`, `ANTHROPIC_DEFAULT_{OPUS,SONNET,HAIKU,FABLE,MYTHOS}_MODEL` — names enumerated, values never read) plus per-project pins in `.claude/settings.json` / `.codex/config.toml`. There is no MCP server anywhere in the chain today.

---

## 3. FIRST-AUDIT COVERAGE MATRIX (honest self-grading against the original 25-part request)

Legend: ✅ COVERED · 🟡 PARTIAL · ❌ NOT COVERED (evidence = where the proof lives).

| Area | Grade | Evidence / residual work |
|---|---|---|
| 1 Repository inventory | 🟡→✅ | Pass 1 inventoried git-tracked + major dirs but did NOT enumerate filesystem-vs-git deltas or count totals → **closed this pass** (§1) |
| 2 File-by-module understanding | ✅ for production path | Full reads: main.py, orchestration×5, core×5(+market_state head), strategy pipeline/scanner/config/base/S01, risk trade_risk/devil_checks(head)+emergency(most), execution orders/tax/tracker(greps+targets), db repository/client(head), research backtest×4/market_data/walk_forward_engine/forecasting×4/universe_loader/registry_adapter(head)/sector_scanner, agents supervisor/bull(greps)/llm_bridge(key), data angelone websocket(now full)/earnings(targeted) |
| 3 Code-level audit | ✅ | Findings C9, H-A1..A4, M-A1..A8, L1..L8 with file:line |
| 4 Structure/naming | ✅ | §2 + §12 tables pass 1 |
| 5 Production/research/test boundary | ✅ | pass-1 §2 classification |
| 6 Archive recovery | 🟡 | Prior adjudications accepted (ENGINE_TRIAGE dispositions); **contents of `Test_archive/`, `tools_archive/`, most of `research_archive/engine_*` (68 files), `scratch/` s01 reports, and `docs_archive/build_docs/**` were listed, not read.** Risk: low (superseded by design), but not individually audited |
| 7 Dependencies/supply-chain | ✅ | lock vs pip-list vs imports; pip check clean; smartapi watch |
| 8 Build-vs-reuse | ✅ (round 1) / extended round 2 | see §5 below |
| 9 API/data-provider discovery | ✅ | broker table + NSE reality + corp-action libs |
| 10 Data audit | 🟡 | Probed representative parquet (schemas/ranges/dups/tz), journals, instrument cache; **did not sweep all 151 parquets programmatically** (per-symbol gap census) — feasible follow-up |
| 11 Quant research validity | ✅ | pins re-verified + NEW survivorship/corp-action findings |
| 12 Backtest realism | ✅ | §7 pass 1 incl. delivery-cost nuance |
| 13 Model audit | 🟡 | Classical baselines + Kronos adapter audited; **TimesFM/Chronos/Toto adapters don't exist yet** (nothing to audit); ML models otherwise absent |
| 14 Agent/LLM audit | ✅ | debate flow, failover ladder, deterministic fallback APPROVE semantics verified this pass |
| 15 Claude Code env | ✅→extended | dot-dir deep pass this pass (§2) |
| 16 Persistent memory | ✅→⚠️ upgraded | ADR-0005 hierarchy verified BUT K-A1 discovered (knowledge layer unversioned) |
| 17 Security | ✅ | secrets scan, TLS, telegram auth, trust boundary; hook blind-spots noted |
| 18 Testing | 🟡 | Both suites executed green; **content-depth**: suite names + key fixtures reviewed, no coverage measurement run, no mutation testing |
| 19 Observability | ✅ | incl. fabricated-telemetry census |
| 20 Performance | 🟡 | Static analysis only (sequential scan, hot-path I/O); **no profiling/benchmarks executed** (correctly deferred per measure-first principle) |
| 21 Reproducibility/recovery | 🟡 | Lockfile+validity-contract verified; experiment manifests absent (known E-wave); **backup posture: none for unversioned layers (K-A1)**; disaster-recovery untested |
| 22 Traceability | ✅ | chain mapped; learning-loop break identified |
| 23 Complexity | ✅ | |
| 24 Git history | 🟡 | log/blob/filename forensics done; **full-history content secret-scan not performed** (pattern scan on working tree only; one historical `.webui_secret_key` found by filename) |
| 25 Final classification | ✅ | §12 pass 1 |

**Explicitly NOT covered by either pass (registered, not silently dropped):** live behavior of Angel One re-auth under a real daily token rollover (unit-tested only, never observed live); Supabase remote schema state (N6, owner-blocked); whether Angel One ToS permits long-term local retention of minute bars; actual TSFM performance on NSE data (requires torch install decision); Windows Task Scheduler/service deployment state (verified: nothing registered today); pip-audit CVE scan (would require installing a package — prohibited this pass).

---

## 4. GAP-CLOSING VERIFICATIONS COMPLETED THIS PASS (new evidence)

1. **C8 feed-loss fixes verified in full** ([websocket.py](../../../mjonai-build/data/angelone/websocket.py)): disconnect clears ALL live caches (fail-closed downstream), `_connection_confirmed` gate prevents fake reconnect success, jittered backoff, chunked subscribe ≤400/packet, re-auth hook at attempt 3. The final recovery-failure alert is **honest** ("Live feed DOWN … no fallback feed exists"). ⇒ Refines H-A2: the false claim exists **only** in `orchestration/websocket_supervisor.py` message strings — pure text fix, mechanics sound.
2. **M8 tracker SHORT fallback: FIXED** (direction-aware ±2%/±5% defaults, [tracker.py:272-281](../../../mjonai-build/execution/tracker.py)) — this M-item from the 08-24 audit can be struck.
3. **Tranche parent-decrement fix verified real** (tracker :176-182) — closes another prior M-item.
4. **H12 earnings gate verified at module level** (raises `EarningsDataUnavailableError` unless RESEARCH opts into permissive degraded mode).
5. **Registry adapter purity confirmed** ("pure translator" docstring + neutral-context values echoed to metadata only); residual confirmed: `NEUTRAL_VIX=13.5` permanently pins S04's adaptive threshold in research runs.
6. **LLM outage semantics pinned precisely**: bridge falls through Groq→Gemini→OpenAI-compat→deterministic scorer which can emit APPROVE (net_confidence ≥65, capped logic) with `is_deterministic_fallback=True` recorded — approvals during full LLM outage are possible by design and distinguishable only in logs/DB, not alerts (M-tier, unchanged verdict).
7. **Runtime state verified empirically**: no python/uvicorn processes running; no Windows scheduled tasks referencing MJONAI — the standing assumption "runtime not running" is now fact, not assumption.
8. **pip check: no broken requirements** (dependency-graph consistency evidence added).
9. **CODE_REVIEW_FINDINGS.md ledger read** (Sessions #12–#20 tail + structure): documents pattern-memory READER wiring (`8619b98`) — sharpening H-A3 to its precise form: **reader wired, outcome WRITER still absent** (grep re-confirmed zero `update_pattern_outcome`/`upsert_pattern` callers). Also records two process incidents and the 716→722 suite progression matching git history.
10. **Wilder ADX/RSI/RVOL spot-audit**: implementations textbook-correct (`ewm(alpha=1/n, adjust=False)`; RVOL = vol/SMA20).
11. **create_full_snapshot.ps1 classified**: AI-context packer, not backup (feeds K-A1).
12. **`.codex` ↔ `.claude` hooks byte-identical** (diff-verified) — mirrored guardrails confirmed.

---

## 5. ECOSYSTEM RESEARCH ROUND 2 (capability-based; extends TECHNOLOGY_RADAR)

Marketplace scale (verified): official Anthropic plugin directory **250+ plugins**; community catalogs index **~2,000 plugins, 2.6–23K skills, 12.8–16.2K MCP servers**. Scale alone justifies nothing — verdicts below are gap-driven.

| Candidate | Category | License / status | Capability | MJONAI overlap/gap | Verdict |
|---|---|---|---|---|---|
| **`pyright-lsp` official plugin** | Code intelligence | Official dir; pyright already configured (`pyrightconfig.json` present, venv wired) | Diagnostics after every edit; would statically catch unbound-name defects | **Directly addresses the C9 class** (NameError survived 722 green tests). Zero new infra | **ADAPT (highest-value single candidate)** — owner decision; also consider adding `python -m pyright` (already installable offline? needs pkg) or a ruff F821 check to the pre-commit ritual instead |
| repomap-mcp / pitlane-mcp / kungfu / graph-context | Repo indexing, token-budgeted maps | OSS, young, varied | Tree-sitter AST maps, symbol-level reads, PageRank ranking | Repo is ~48k LOC / ~110 source files; grep+MJONAI_DOCS proven sufficient across two full audits | **REJECT-for-now**; trigger to revisit: repo ×3 growth or recurring context pain |
| OpenMemory MCP (Mem0) / Mem0 / Letta / Zep / LangMem | Agent memory | Apache-2.0 (Mem0/Letta); local-first option | Cross-session semantic memory, tiered memory | Violates nothing but adds a server + vector store for a solo repo whose docs are authoritative (ADR-0005) | **REJECT-as-dependency / WATCH** (OpenMemory as the reference if ever needed) |
| Official `supabase` MCP | External integration | Official | DB ops in-session | Would NOT resolve N6 (owner-blocked credentials/DDL; and giving agents DB-write reach widens trust surface) | **REJECT** |
| `security-guidance`, commit/pr-review toolkit plugins | Dev workflow | Official/community | Diff review hygiene | Mild value; house review discipline already ledger-based | **WATCH** |
| whirr / xetrack / LiteMLflow / Dalva | Experiment tracking | OSS, local-first SQLite/DuckDB/JSONL | Manifest-style runs, git+freeze capture | Validates the planned E-wave design (JSONL manifests + duckdb views) rather than replacing it | **BUILD-thin (unchanged)**; keep these as reference designs |
| FastContext (MSR) | Research technique | paper | Exploration-subagent token reduction −60% | Not adoptable directly; validates inline-scoped-grep methodology | INFO |

## 6. TOKEN / CONTEXT OPTIMIZATION (special-focus answer)

**Already has:** consolidated single-truth doc (one file loads instead of many); append-only evidence ledger (no re-derivation); explicit-path test skill avoiding network hangs; session rules preventing duplicate-doc drift; engine-tests skill encodes exact commands; CLAUDE.md operational-only split. This is the "native stack covers 80%" pattern the ecosystem literature describes — verified adequate by two full audits running inline.

**Missing but cheap:** (a) static undefined-name gate (ruff F821/pyright) in the ritual — prevents C9-class escapes AND saves debug cycles; (b) `settings.local.json` allowlist pruning (stale entries cost permission-matching noise, minor).

**Would be overengineering today:** any MCP/vector/AST indexing layer (repo too small), semantic search, context-compression servers, subagent exploration frameworks (and subagents remain credit-blocked anyway per ADR-0006 — though WebSearch worked this session, so ADR-0006's "search unavailable" clause is stale even though its inline-mode directive stands).

---

## 7. AI DEV CHAIN AUDIT (Desktop → CLI → config → gateway → model → tools → memory → repo)

```
Claude Code Desktop (host app; session mgmt, preview tools)
   └─ CLI/runtime (CLAUDE_CODE_* env; provider-managed auth headers)
        └─ Machine-level env (Windows user env — OWNER OF ROUTING):
             ANTHROPIC_BASE_URL=<gateway>, ANTHROPIC_DEFAULT_*_MODEL=anthropic/stealth/ox-alpha
        └─ Project overrides: .claude/settings.json (pins ×3), .codex/config.toml (pins ×3)
        └─ Hooks: block_secrets.py (PreToolUse Write|Edit|NotebookEdit; fails open on malformed input;
                  guards Write/Edit only — shell redirection unguarded)
        └─ Skills: engine-tests (project, mirrored ×3)   MCP: NONE   Plugins: NONE
        └─ Auto-memory: ~/.claude/projects/D--MJONAI/memory (convenience layer only)
        └─ Repository truth: MJONAI_DOCS.md + CLAUDE.md + docs_archive + planning  ← ⚠️ OUTSIDE ANY GIT REPO (K-A1)
```

**Ownership map:** routing/model selection = machine env + project pins (vendor-coupled); session mechanics = host app; safety guardrail for edits = repo-local hook files (portable, plain Python); authoritative knowledge = repo-tree markdown (portable, vendor-neutral) **but unversioned**; convenience recall = user-profile memory (disposable).

**Survivability matrix (tested conceptually, evidence above):**
| Event | Survives? | Because |
|---|---|---|
| Claude reinstall | ✅ project knowledge | markdown in D:\MJONAI; memory dir disposable |
| Model replacement | ✅ | pins are env/settings, docs model-agnostic |
| Gateway/OpenRouter swap | ✅ functionally | single BASE_URL var; ADR-0006 documents fallback channels |
| Machine loss | ❌ **knowledge layer at risk** | K-A1: docs/ADRs/evidence not in any VCS; snapshots script ≠ backup; only pushable artifact is mjonai-build (itself **17 commits ahead of origin**) |
| Memory-file corruption | ✅ | MEMORY.md index regenerable; conflicts resolve toward layer 1 |

**Single points of failure ranked:** 1) unversioned knowledge layer (K-A1); 2) unpushed commits; 3) machine-local `.env.master` (single copy of 71 secrets — unrecoverable if lost; no backup mechanism exists or is permitted to exist by policy → owner should hold an off-machine copy); 4) ox-alpha single-model pin (402-class outages stall fan-out; inline mode mitigates).

---

## 8. SECURITY GAP RE-VERIFICATION (deltas only)

Pass-1 posture re-affirmed. New/confirmed specifics: hooks identical across .claude/.codex (diff ✓); hook fails open on malformed JSON (documented tradeoff) and cannot intercept Bash redirection; no MCP/plugins anywhere ⇒ no MCP-permission surface to audit; user-level Claude dir contains no credentials; machine env carries routing vars (values never read; names only). Conceptual test — *"can the dev environment accidentally reach live trading?"* — answer unchanged: **No**, triple-gated (dual-key env + absent broker driver + paper-default SYSTEM_MODE), and no tool in the chain has network reach to broker order endpoints except the runtime process itself, which is not running (verified).

---

## 9. ARCHIVE / DATA GAP VERIFICATION

Areas listed-but-not-read in pass 1, now dispositioned:
- `research_archive/engine_*` (68 files) + `Test_archive/` (10) + `tools_archive/` (2): ENGINE_TRIAGE dispositions + absorption record cover their origin; contents remain individually unread. Value class: HISTORICAL/REPRODUCIBILITY. Recommendation unchanged: PRESERVE (house rule), no salvage expected — confidence: medium-high, not verified line-by-line.
- `scratch/s01_*.md|csv|log`: simulation evidence for the S01 minute-pipeline era — HISTORICAL value only; recommendation UNGIT + preserve on disk.
- `docs_archive/build_docs/**` (architecture/debt registers from pre-absorption era): superseded by MJONAI_DOCS + ledgers; spot-checked titles only. ARCHIVE.
- `mjonai-dashboard/` backend route bodies: H11 adjudication accepted from 08-24 audit; not re-read (stack superseded). ARCHIVE-pending-owner.
- Journals/logs dated dirs: sampled via schema probes; full-content review unnecessary (telemetry, small).

---

## 10. TARGET-ARCHITECTURE READINESS (stage table; no redesign)

| Stage | Implemented? | Owner module(s) | Known problems | Missing | Uncertainty |
|---|---|---|---|---|---|
| DATA | partial-split | live=yfinance-direct; research=providers+parquet | two stacks (pass-1 §5); corp-action gap; survivorship | point-in-time universe; minute source (Fyers/Dhan identified) | angel ToS on retention |
| DATA QUALITY | yes | freshness enums, coverage-aware cache, staleness gates | MQI baseline free-points; get_session_state fail-open | cross-stack tz convention | — |
| FEATURES | partial | indicator_values (RVOL/ADX/RSI/ATR…), sector-breadth cross-section, pattern-memory reader | writer absent (H-A3) | OI/RS/MTF sources (honestly None today) | — |
| MARKET STATE | yes | market_state, MQI, time_utils | duplicated calendars; hardcoded MPC≤2028 | automated event-calendar source | — |
| MODELS | classical only | forecasting/classical | none run live | TSFM adapters blocked on torch decision | Kronos-on-NSE performance unknown |
| FORECAST | research-only | pipeline_gate | first verdict negative (honest) | nothing until edge shown | — |
| SIGNALS | yes | scanner+pipeline gates | **C9 crash latent**; funnel counters dead | quorum rule (absent by design-doc) | — |
| STRATEGIES | yes | registry S01–S12 | 6 emit no stop; S12 pillar-4 fiction; TF fiction on daily bars | intraday-native operation | — |
| PORTFOLIO | minimal | limits ladder, sector caps | caps-key mismatches; static TOTAL_CAPITAL anchor | true portfolio construction (deliberately none) | — |
| RISK | yes | trade_risk/devil/emergency/behavioral | kill-line truthing (H-A1); monitoring fail-open on DB outage | lifetime leg implementation | — |
| EXECUTION | paper-complete | orders dispatcher | broker driver absent (H-A4); close-all entry-price fallback | SmartAPI driver + reconciliation | fill semantics untestable pre-live |
| LEDGER | yes | Supabase façade + journals | replay unscheduled; N6 remote drift pending owner | rotation | — |
| EVALUATION | research-strong | analytics + statistical_validation | live-reporting metric trio divergence (prior audit) | unified reporting consumer | — |
| LEARNING | **broken** | — | no writers (H-A3) | forward-return job body, pattern writer, weight recalibration | — |

Verdict: **sufficient understanding exists to define a target architecture when the owner chooses**; the only stages needing further investigation before design are DATA (minute-source spike) and EXECUTION (driver semantics), both already on the wave plan.

---

## 11. TRACEABILITY GAPS (delta from pass 1 §14)

Answerability of *"why did MJONAI make this decision?"* for a given trade TODAY: entry context ✅ (signal_intelligence: factors/devil checks/bull-supervisor verdicts/vix/mqi/ltp_source) → sizing ✅ (costs itemized, slippage_bps, tranche geometry) → lifecycle ✅ (tracker updates, MAE/MFE) → settlement ✅ (parent rollup) → **outcome labels ❌ (forward returns never computed)** → learning ❌ (H-A3). Plus two blind spots: forecast stage contributes nothing traceable yet (by design), and RESEARCH-mode trades carry `research_valid` flags whose population path wasn't independently re-verified this pass (UNKNOWN-U6).

---

## 12. EXPLICIT UNKNOWN REGISTER

| # | Unknown | Why unknown | What would resolve it | Risk if left |
|---|---|---|---|---|
| U1 | Live behavior of WebSocket re-auth at real Angel One daily rollover | Unit-tested only; requires observing a real rollover | One monitored live session day | Recovery could still fail in field conditions (gates fail closed, so capital-safe, but availability loss) |
| U2 | Supabase remote schema drift (N6) details | Owner-blocked; credentials untouchable by policy | Owner runs migration; then insert-path test | Paper rows keep buffering to WAL only |
| U3 | Angel One ToS on long-term local minute-data retention | Legal text not audited (out of scope) | Owner/legal read of API terms | Compliance exposure if retention continues |
| U4 | TSFM (Kronos/TimesFM/Toto) actual edge on NSE | torch not installed; adoption bar intentionally high | Torch decision + benchmark runs per ADR-0002 | None (status quo honest) |
| U5 | True survivorship-bias magnitude in existing backtests | Requires point-in-time constituent data acquisition | Data spike (niftyindices historical constituents) | Overstated historical edges inform future decisions |
| U6 | `research_valid` flag population path completeness | Flag seen in schema/docs; write-path not traced end-to-end this pass | 30-min targeted grep/read | Minor: research-label trust |
| U7 | Whether any Windows autostart existed historically for main.py | schtasks query shows none today; history not auditable via schtasks | Owner recollection / old VM images | Low |
| U8 | Full git-history content secrets scan | Would need `git log -p` sweep (time; low expectation) | Targeted history grep session | Low (repo private; one removed webui key known) |
| U9 | CVE status of 92 pinned packages | pip-audit not installed; installing prohibited this pass | Owner-approved `pip-audit` run | Medium-long-tail (supabase/httpx/yfinance are network-facing) |
| U10 | dashboard formal retirement date | Owner call pending (ADR-0007 supersedes) | Owner decision | Doc-drift only |

---

## 13. FINAL GAP REPORT

**A. Covered successfully (both passes):** production code path (runtime→scanner→pipeline→risk→orders→ledger→research), quant methodology pins, cost-engine unification, security boundaries, dependency reality, data-store schemas, git forensics, dev-env chain, ecosystem research (two rounds), architecture readiness.

**B. Only partially covered:** archive file contents (listed, not read — low risk), all-151-parquet programmatic sweep, test-suite content depth (green-run + fixture reads, no coverage metrics), performance measurement (static only), git-history content scan, blueprint full-text (headings + targeted sections), `mjonai_intelligence/` internals (frozen; untouched-by-design), dashboard internals (superseded).

**C. Missed by pass 1, found this pass:** **K-A1 knowledge layer outside version control** (the biggest one); runtime-state empirical verification (not running); `create_full_snapshot.ps1` misclassification risk (packer ≠ backup); CODE_REVIEW_FINDINGS ledger depth (Sessions #12–#20 refine several claims); M8 + tranche-decrement prior-M-items now verifiably fixed; websocket honest-alert isolating H-A2 to text.

**D. Assumed rather than verified in pass 1, now verified:** runtime-not-running (assumed → tasklist/schtasks verified); hooks mirrored (assumed → diff verified); user-config minimalism (assumed → enumerated); pip consistency (assumed → pip check clean); H12/module-level, registry-adapter purity, Wilder math (accepted → now code-verified).

**E. Still unknown:** register §12 (U1–U10), dominated by owner-blocked externals (U2, U4, U10) and deliberate-deferred measurements (U5, U9).

**F. Additional research performed:** marketplace/plugin scale, code-intel MCP quartet, agent-memory frameworks (Mem0/Letta/Zep/LangMem/OpenMemory), context-optimization techniques (FastContext/repomap/pitlane/kungfu/graph-context), lightweight experiment trackers (whirr/xetrack/LiteMLflow/Dalva).

**G. New technologies discovered:** pyright-lsp official plugin (top candidate), OpenMemory MCP, Toto-2.0/FinCast (pass-1 addendum), repomap/pitlane/kungfu/graph-context, whirr/xetrack/LiteMLflow.

**H. Recommendations changed:** claude-mem ADAPT-later → **REJECT/WATCH** (license flip, pass-1 addendum); code-intel MCPs "unverified-WATCH" → **REJECT-for-now with explicit trigger**; E-wave "MLflow-or-manifests" → **manifests confirmed as industry direction, BUILD-thin stands**; NEW: static-analysis-in-ritual recommendation born from C9; NEW: K-A1 version-the-knowledge-layer (owner decision).

**I. Recommendations unchanged/valid:** all ADR-0001..0007; fix-order ladder (C9 → kill-line truthing → REST-theater text → learning-loop wave → minute-source spike → torch decision); keep/build list; reject list with reasons.

**J–K. Can the repository be considered fully audited?** For **decision-making purposes: yes — SUBSTANTIALLY COVERED (upper bound)**. Every production-path component has been read; every claim in MJONAI_DOCS has been tested against code; inventory reconciles completely; security posture is evidenced. It is **not "FULLY COVERED"** in the absolute sense because: (i) archive/test internals are sampling-verified, not exhaustively read; (ii) five unknowns require owner action or live observation (U1/U2/U4/U9/U10); (iii) dynamic behaviors (real rollover, live fills, calendar-outage postures) can only be verified in operation; (iv) no coverage-measured test audit was performed. These residuals are registered above with resolution costs and do not undermine the audit's conclusions.

**Final assessment: SUBSTANTIALLY COVERED.**

---

*Generated 2026-08-25, second pass. Zero modifications made to project, configuration, memory, or Git state during this pass.*
