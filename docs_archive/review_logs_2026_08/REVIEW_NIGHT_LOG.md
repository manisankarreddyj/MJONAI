# OVERNIGHT REVIEW — NIGHT LOG (2026-08-23)

## Rules in force (self-imposed, user-approved)

1. Branch: `engine-absorption` only. Never touch master. No push. No merge.
2. `credentials/` — never opened. Guard hook also blocks it.
3. Program code: **READ-ONLY tonight**. Only these may be written:
   - `CODE_REVIEW_FINDINGS.md` (append-only findings)
   - `REVIEW_NIGHT_LOG.md` (this progress file)
   - `REVIEW_NIGHT_REPORT.md` (final morning report)
   - `.md` truth-fixes only where docs state something now-false
4. Helper agents: read-only instructions in every prompt.
5. Every helper finding is spot-verified by me before being logged as CONFIRMED.
6. Progress written to this file after every wave. If the machine sleeps mid-run, this file shows exactly where we stopped.

## Wave checklist

- [x] Wave A1: main.py + orchestration/
- [x] Wave A2: data/angelone/ + feed_manager + data/market/
- [x] Wave A3: risk/
- [x] Wave A4: execution/ + db/
- [x] Wave A5: strategy/ (pipeline, scanner, registry base+indicators)
- [x] Wave A6: agents/ + communication/
- [x] Wave A7: core/ + configs/ + intelligence/ + knowledge/
- [x] Wave A8: options/ + mjonai_intelligence/ (light, frozen module)
- [x] Wave A9: analytics/ + storage/ + research/ (covered by this week's deep work; tests audit substituted)
- [x] Wave A10: tests/ quality audit
- [x] Wave B: 12 strategy math verdicts
- [x] Wave C: dashboard
- [x] Wave D: security/dotfiles/config sweep
- [x] Wave E: archive tag-check + doc truth-fixes
- [x] Final: REVIEW_NIGHT_REPORT.md

## Progress notes

- 23:5x — Night run started. Helpers confirmed working on ox-alpha.
- Wave A1 (orchestration): DONE - 12 findings (1 new P0 lock-file bug; old P0-7 already fixed).
- Wave A3 (risk): DONE - 14 findings (2 new P0: soft-stop dead in LIVE, kill-line drawdown math broken). Logged to root CODE_REVIEW_FINDINGS.md.
- Waves A2+A4 DONE: A2=12 findings (P0 depth deadlock), A4=14 findings (6 P0s in order path - worst wave). Logged.
- Waves A5+A6 DONE: A5=13 findings (P0: regime filter bypassed + 14mo refetch every cycle), A6=13 findings (P0: telegram fail-open auth, debate advisory-only, golden rules not implemented). Logged.
- Waves A7+A8 DONE: A7=12 findings (expiry-day wrong since Sep 2025!, env import-order, DST bug, fail-open holidays), A8=3 findings (charm sign flip). Logged.
- Wave B DONE: 12 verdicts - 0 SOUND, 6 MINOR, 4 FLAWED (S03,S05,S09,S10), 1 UNUSABLE (S08). Cross-cutting: missing-data-passes-gates pattern, warmup bias, doc-code rot.
- Waves C+D DONE: C=10 (dashboard cannot boot! hardcoded API key in browser bundle), D=9 (code clean of secrets; config gaps).
- ALL WAVES COMPLETE. 112 findings. Report at REVIEW_NIGHT_REPORT.md. Committing findings/docs locally (no push per rules).
- Session 3 fix round COMPLETE: commit 499526b. 96 scoped tests green, full suite 630 passed. Dashboard fixes NOT committable (mjonai-dashboard is outside the git repo - noted).
- F4 (my part) DONE: expiry Tuesday constant, US DST, holiday fail-closed w/ env override. Test fixtures updated to Tuesday rule. 33 tests green. Awaiting 2 helpers (websocket/token + market gating).
