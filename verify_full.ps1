<#
.SYNOPSIS
  MJONAI full verification — the ONE command to run on the machine where the
  credentials live (D:\MJONAI).

.DESCRIPTION
  What it does, in order:
    1. Shows the repo location, time, git branch/commit (for the record).
    2. Picks the repo venv (.venv\Scripts\python.exe) when present, else
       system Python (with a warning).
    3. Confirms credentials\.env.master EXISTS (checks the filename only —
       it never reads, prints, or transmits any secret; the engine loads
       the file itself at test time).
    4. Runs the full test suite:  pytest tests --ignore=tests\research -q
       (tests\research is gated behind a real --run-research marker option and
       is intentionally excluded here, per house rules: never bare pytest).
    5. Prints an ALL GREEN / FAILURES banner.
    Exit code = pytest exit code (0 = all green), so it composes with
    automation or a future CI step.

.NOTES
  WHY THIS EXISTS: the Arena.ai sandbox cannot reach Supabase (TLS is
  severed) or the Angel One API (DNS is blocked), so the ~8 environment-
  dependent tests can ONLY pass on this machine. A run here is the
  canonical green reference (canonical reference: 724/0 on 2026-09-01,
  suite has since grown to ~860 tests).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\verify_full.ps1
#>
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "=================================================="
Write-Host " MJONAI FULL VERIFICATION"
Write-Host "=================================================="
Write-Host " Repo   : $PSScriptRoot"
Write-Host " Time   : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"

# --- Python selection (prefer repo venv) -------------------------------
$repoVenv = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (Test-Path $repoVenv) {
    $py = $repoVenv
    Write-Host " Python : repo venv"
} else {
    $py = "python"
    Write-Host " Python : system (repo .venv not found - results may differ)" -ForegroundColor Yellow
}
& $py --version

# --- Repo state (for the record) ----------------------------------------
$branch = git rev-parse --abbrev-ref HEAD 2>$null
$head   = git rev-parse --short HEAD 2>$null
if ($branch) {
    Write-Host " Git    : $branch @ $head"
}

# --- Credentials presence (filename only - NEVER contents) --------------
$envFile = Join-Path $PSScriptRoot "credentials\.env.master"
if (Test-Path $envFile) {
    Write-Host " Creds  : credentials\.env.master present (engine loads it; never shown)" -ForegroundColor Green
} else {
    Write-Host " Creds  : credentials\.env.master MISSING - env-dependent tests will fail" -ForegroundColor Red
}
Write-Host ""

# --- The suite -----------------------------------------------------------
Write-Host "--------------------------------------------------"
Write-Host " Running full suite (the ~50 second part)..."
Write-Host "--------------------------------------------------"
& $py -m pytest tests --ignore=tests\research -q
$code = $LASTEXITCODE

Write-Host ""
Write-Host "=================================================="
if ($code -eq 0) {
    Write-Host " RESULT : ALL GREEN" -ForegroundColor Green
} else {
    Write-Host " RESULT : FAILURES PRESENT (exit code $code)" -ForegroundColor Red
}
Write-Host "=================================================="
exit $code
