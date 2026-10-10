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

## Output
Findings ranked (Critical/High/Medium/Low) each with `file:line` + a concrete remediation, and an
explicit note of what is **enforced vs gap**. **Do not silently patch a security finding** — report,
then fix under `review-diff` with the owner's approval.
