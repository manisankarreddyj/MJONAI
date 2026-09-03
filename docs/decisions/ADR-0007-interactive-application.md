# ADR-0007: Interactive application strategy — API-first, web PWA now, Android-ready

**Status:** ACCEPTED (2026-08-24, owner set end goal: interactive application on BOTH web and Android)

## Terminology (owner-corrected)
Not "dashboard". The product surface is the **MJONAI interactive application**; targets: web application AND Android app.

## Context
Current state: FastAPI backend (`mjonai-dashboard/backend`, ~10 route modules incl. websocket_manager) + orphaned Next.js `frontend_src` (8 components, NO package.json → never boots; audit H11 called the UI dishonest). Push-style alerts ALREADY exist via Telegram bot + commands and Discord webhooks.

## Decision
1. **FastAPI service = the single MJONAI application API.** Its route modules move conceptually from "dashboard backend" to product API; auth hardened; every payload served from Supabase/repository façade — never recomputed UI-side fiction (fixes H11 by construction).
2. **Web first:** replace Next.js orphan with server-rendered HTML + HTMX + PWA manifest served BY the FastAPI service (single process, single deploy). Installable on Android via Add-to-Home-Screen. No Node toolchain.
3. **Android native deferred, door open:** if/when PWA limits bite (e.g., background refresh), add an Expo/React-Native shell consuming the SAME API. Because (1) is API-first, this requires zero backend rework.
4. **Alerts stay on Telegram/Discord** — they are the push channel; the interactive application is for rich views + control, not notification plumbing.
5. Old `frontend_src` archived to preserve history (house rule: never delete); Next.js removed from all setup docs.

## Alternatives rejected
- Revive Next.js PWA: two stacks (Node+Python), double deploy surface, orphan already rotten.
- Flutter/RN-everything now: foreign stack, cost before value.
- Telegram-only: fails the stated web+Android end goal.

## Consequences
One language (Python) for the whole runtime+UI; websocket_manager reused for live tiles; work scheduled AFTER data-truth wave G4 so the app renders honest numbers from day one.

## Amendment (2026-08-25, evening) — v3 direction set

Owner critique accepted: v1/v2 shipped a monitoring ADMIN PANEL, not the
"interactive application" the end goal names. v3 tiers agreed by owner
delegation (owner opted to delegate the ordering):

1. EXPLORATION first — trade decision-chain drill-down, strategy detail
   pages, signal evidence viewer (read-only over existing records).
2. ACTION second — kill-line manual reset, strategy enable/disable,
   RESEARCH->PAPER transitions, run-now job triggers, bounded data ops.
   Safety frame: the app requests state changes; deterministic risk gates
   stay in the runtime; app never sizes orders, touches the broker path,
   or transitions toward LIVE (dual-key stays env-only). Every action
   authenticated, confirmed, and audit-logged.
3. LIVE PUSH third (SSE/websocket positions & risk events).
4. AI ASSISTANT last — llm_bridge Q&A over records with mandatory row
   citations; honesty rules apply to the assistant.

v1/v2 remain valid as the observation layer; v3 layers interaction on top.
