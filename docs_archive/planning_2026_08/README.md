# planning_2026_08 — Superseded Working Drafts (moved 2026-09-03)

House rule: preserved, never deleted. This folder is the 2026-08-24/25 blueprint-review
engagement output set, moved from `planning/` per ADR-0005's merge-then-supersede rule
(the step that had lapsed — see `docs_archive/review_logs_2026_09/DOC_AUDIT_2026_09_03.md`).

| File | Status at move | Disposition |
|---|---|---|
| `CURRENT_STATE.md` | 08-24 audit snapshot; defect position (C1–C3, C7, C8, N1) all since fixed | Superseded — ledgers of record are in `review_logs_2026_08/` + MJONAI_DOCS §13 |
| `REUSE_AUDIT.md` | Component verdicts; **3 were wrong/stale** (intelligence "dead duplicate", options "dormant", knowledge verdict was right) | Superseded by the 2026-09-01 file audit + 2026-09-03 doc audit; knowledge/ actually archived on the back of it (R3) |
| `TARGET_ARCHITECTURE.md` | Target shape matched as-built; owner-delegated decision 2 (merge `intelligence/` → `macro_check`, archive) was based on the wrong dead-duplicate verdict | Decision 2 **reversed 2026-09-03 (R2)**: `intelligence/` kept as research factor library. Shape + 4-ports remain the reference (ADR-0004). |
| `TECHNOLOGY_RADAR.md` | Dated external-tech evidence (push dates/licenses as of 08-24) | Historical evidence; two live watch-items extracted to MJONAI_DOCS §9 (smartapi-python staleness, dhanhq as Broker-port second source) |
| `supabase/` | 08-25 migration runbook + diff + DDL draft — **executed** (N6 closed 2026-08-25, MJONAI_DOCS §11) | Evidence of record for the schema-unification migration |
| `fno/` | 08-25 F&O data spikes — **executed** (dataset adopted, rules live in §9) | Evidence of record; the binding OI-unreliability rule already lives in MJONAI_DOCS §9 |

`planning/decisions/ADR-0001…0007` stay in `planning/` as the frozen decision records
(status lines refreshed 2026-09-03). The original GPT blueprint lives one level up:
`docs_archive/MJONAI_MASTER_IMPLEMENTATION_BLUEPRINT.md` (its own banner: "not an
implementation plan").
