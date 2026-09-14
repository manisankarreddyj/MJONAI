# ARCHIVE STATUS: PRESERVED (moved 2026-09-14)

Retired unwired agent modules, quarantined per the 2026-09-14 boardroom
retirement ruling (Decisions 4–5: the "five specialists" design was fiction —
real authority is the Supervisor's 5 deterministic rules + Bear veto + Gate 5
devil checks; `db/agents.py` scoreboard is BULL/BEAR/SUPERVISOR only).

- `quant_auditor.py` — zero production consumers (tests-only + `agents/__init__.py`
  re-export). Not part of the wired pipeline.
- `dual_model_ensemble.py` — zero production consumers (tests-only).
- `test_quant_auditor_agent.py` + `test_dual_model_ensemble.py` — their fixtures,
  preserved next to the modules they exercised.

Nothing here is imported by live code (verified by AST scan of `mjonai/` + `apps/`
on 2026-09-14). House rule: never deleted; read-only reference.

Note: `debate_room.py` and `macro_specialist.py` were NOT moved — they are
production-wired via the `/ai` + `/debate` Telegram commands
(`telegram_commands.py` → `handle_ai` → `conduct_adversarial_debate`).