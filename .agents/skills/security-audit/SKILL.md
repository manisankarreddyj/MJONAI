---
name: security-audit
description: Focused security pass over MJONAI's real attack surface — secrets in source, .env handling, Supabase RLS, API/Telegram auth, egress + TLS verification, Docker image hygiene, and dependency CVEs. Use for a security review, before a release, or when the user asks for /cso-style audit. Report-only; never silently fix a security finding.
---

# MJONAI /security-audit — targeted, not generic

This is a personal, secrets-bearing, paper-trading system that will eventually touch a broker and
Supabase service-role credentials. Audit the surface that actually exists — not a generic OWASP checklist.

## Surface to audit (with `file:line` evidence in the report)

1. **Secrets in source.** `gitleaks` (`.gitleaks.toml`, CI `secrets-scan`) + grep for `api_key|token|secret|password|TELEGRAM_|SUPABASE_|SMARTAPI_` in `mjonai apps tools`. The root `.env` is gitignored + never read into context; only `.env.example` (redacted template) is tracked. Write-path blocker: `.claude/hooks/block_secrets.py` + `.codex/hooks/block_secrets.py` (mirror both).
2. **DB / Supabase.** `mjonai/db/rls.py` is deny-by-default (RLS *ENABLE + FORCE*, zero policies) — confirm no writer bypasses it. `get_supabase_client` surfaces an ERROR on anon-key fallback (RLS would silently deny writes). Service-role key must never reach the client/web. DDL migrators require `SUPABASE_POOLER_URL` + service-role and refuse otherwise.
3. **API / bot auth.** Web `verify_api_token` is **constant-time** (`secrets.compare_digest`) and every `/api/*` + `/api/v1/control/*` + `/api/dr/*` + `/api/research/*` + `/ws/stream` carries it; a remote-exposed server with no token is **503 fail-closed** (`/api/health/*` stays public by design). Telegram `_is_authorized` returns False when `TELEGRAM_CHAT_ID` is unset; every command re-checks.
4. **Egress / TLS / subprocess.** Flag any `ssl.CERT_NONE` / `verify=False` (a repo pattern to grep). `subprocess`/`os.system` calls; `shell=True`; YAML/`eval`/`pickle` on untrusted data; unauthenticated outbound fetches. Note any feed that hits the network per request.
5. **Supply chain.** `pip-audit` / `osv-scanner` against `requirements-lock.txt` when available; pinned toys; the stale `smartapi-python` watch (ADR-0004). `.dockerignore` must keep `.env`, data, tests, and keys out of image layers; rootless user in `infra/Dockerfile`.
6. **Kill-switch / live gate.** dual-key `SYSTEM_MODE==LIVE` **and** `LIVE_EXECUTION_AUTHORIZED`; missing broker driver fails closed; `SEBI_ALGO_TAG` must be set before any live (operator prerequisite).
7. **Black-box pass against the running PWA** (clean-room from the strix
   web-app-pentesting workflow, Apache-2.0 — workflow reimplemented, no code
   copied). Run `apps/web/run_app.py` locally (default 127.0.0.1:8787) and
   probe the live surfaces — never assume the code reads as it behaves:
   - **Auth scope.** Every `/api/*`, `/api/v1/control/*`, `/api/dr/*`,
     `/api/research/*`, `/ws/stream` must 401/403 without the bearer token;
     remote-exposed (`MJONAI_APP_HOST` set) with no token must 503 on all API;
     `/api/health/*` stays public by design. Try a wrong token (must fail —
     constant-time compare must not leak validity via timing or message).
   - **Cross-mode IDOR.** With a valid token, request PAPER records while the
     engine runs RESEARCH and vice versa — a mode-scoped read must never
     return another mode's book (`get_open_trades` mode scoping, DR reconcile
     mode scoping). This is the highest-impact class here; prove each claim
     with a live request/response pair, not a code quote.
   - **Fail-closed fetch behavior.** Stop the API and confirm every data page
     renders its `{available:false, reason}` state (dashboard: "showing last
     values, retrying") — never "connected", never a silent empty panel.
   - **Rate/velocity.** Burst the order-adjacent surfaces (control, DR
     reconcile) and confirm the SEBI 10-OPS posture + no unthrottled
     state-changing endpoint.
   - **Contract.** Report per-finding live PoCs (request → status → body);
     exit posture: 0 = no validated finding in the probed scope (state the
     scope — it is not proof of full coverage), 2 = validated finding with
     PoC, 1 = harness/setup failure. Fixes land under `review-diff` and are
     re-probed before closing — re-testing is the only confirmation.

## Output
Findings ranked (Critical/High/Medium/Low) each with `file:line` + a concrete remediation, and an
explicit note of what is **enforced vs gap**. **Do not silently patch a security finding** — report,
then fix under `review-diff` with the owner's approval.
