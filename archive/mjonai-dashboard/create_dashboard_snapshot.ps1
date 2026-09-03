# ============================================================
# MJONAI DASHBOARD SNAPSHOT
# ============================================================
# Creates ONE complete snapshot containing:
#   1. Project tree
#   2. Complete file contents
#
# Root:
#   D:\MJONAI\mjonai-dashboard
#
# Excluded:
#   .git
#   .pytest_cache
#   __pycache__
#   node_modules
#   dist
#   build
#   .next
#   coverage
#   .venv
#   venv
#   env
#   cache directories
#   generated snapshot files
#
# Security:
#   Secrets, passwords, tokens and private keys are REDACTED.
#
# IMPORTANT:
#   ASCII-only tree characters are used to avoid PowerShell
#   encoding/parser problems.
# ============================================================

$ErrorActionPreference = "Stop"

# ------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------

$Root = "D:\MJONAI\mjonai-dashboard"

$SnapshotFile = Join-Path $Root "FULL_MJONAI_DASHBOARD_SNAPSHOT.txt"

$ExcludedDirectories = @(
    ".git",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".next",
    "coverage",
    ".venv",
    "venv",
    "env",
    ".cache",
    "cache",
    ".turbo",
    ".parcel-cache"
)

$ExcludedFiles = @(
    "FULL_MJONAI_DASHBOARD_SNAPSHOT.txt",
    "FULL_MJONAI_DASHBOARD_TREE.txt"
)

# ------------------------------------------------------------
# VALIDATE ROOT
# ------------------------------------------------------------

if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
    Write-Host "ERROR: Dashboard root not found:" -ForegroundColor Red
    Write-Host $Root
    exit 1
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "MJONAI DASHBOARD SNAPSHOT" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Root: $Root"
Write-Host ""

# ------------------------------------------------------------
# PATH EXCLUSION
# ------------------------------------------------------------

function Is-ExcludedPath {
    param(
        [string]$FullPath
    )

    $relative = $FullPath.Substring($Root.Length).TrimStart('\')

    if ([string]::IsNullOrWhiteSpace($relative)) {
        return $false
    }

    $parts = $relative -split '\\'

    foreach ($part in $parts) {
        if ($ExcludedDirectories -contains $part) {
            return $true
        }
    }

    $fileName = Split-Path -Leaf $FullPath

    if ($ExcludedFiles -contains $fileName) {
        return $true
    }

    return $false
}

# ------------------------------------------------------------
# SECRET REDACTION
# ------------------------------------------------------------

function Redact-Secrets {
    param(
        [string]$Text
    )

    if ([string]::IsNullOrEmpty($Text)) {
        return $Text
    }

    $result = $Text

    # --------------------------------------------------------
    # 1. ENVIRONMENT VARIABLE ASSIGNMENTS
    # --------------------------------------------------------

    $secretNamePattern =
        '(?i)(api[_-]?key|apikey|secret[_-]?key|secret|password|passwd|pwd|token|access[_-]?token|refresh[_-]?token|auth[_-]?token|bot[_-]?token|private[_-]?key|client[_-]?secret|database[_-]?url|db[_-]?password|aws[_-]?secret|aws[_-]?access[_-]?key|credential|credentials)'

    $result = [regex]::Replace(
        $result,
        "(?m)^(\s*(?:export\s+)?$secretNamePattern\s*=\s*)(.*)$",
        '$1[REDACTED]'
    )

    # --------------------------------------------------------
    # 2. JSON / YAML / TOML STYLE SECRETS
    # --------------------------------------------------------

    $result = [regex]::Replace(
        $result,
        '(?i)("?(?:api[_-]?key|secret[_-]?key|secret|password|passwd|pwd|token|access[_-]?token|refresh[_-]?token|client[_-]?secret|private[_-]?key)"?\s*[:=]\s*)("[^"]*"|''[^'']*''|[^,\r\n}]+)',
        '$1[REDACTED]'
    )

    # --------------------------------------------------------
    # 3. AUTHORIZATION HEADERS
    # --------------------------------------------------------

    $result = [regex]::Replace(
        $result,
        '(?i)(Authorization\s*[:=]\s*(?:Bearer|Basic)\s+)[^\s\r\n"]+',
        '$1[REDACTED]'
    )

    # --------------------------------------------------------
    # 4. BEARER TOKENS
    # --------------------------------------------------------

    $result = [regex]::Replace(
        $result,
        '(?i)(Bearer\s+)[A-Za-z0-9._~+/=-]+',
        '$1[REDACTED]'
    )

    # --------------------------------------------------------
    # 5. PRIVATE KEY BLOCKS
    # --------------------------------------------------------

    $result = [regex]::Replace(
        $result,
        '-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----',
        '[REDACTED PRIVATE KEY]',
        [System.Text.RegularExpressions.RegexOptions]::Singleline
    )

    # --------------------------------------------------------
    # 6. JWT TOKENS
    # --------------------------------------------------------

    $result = [regex]::Replace(
        $result,
        '\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b',
        '[REDACTED JWT]'
    )

    # --------------------------------------------------------
    # 7. TELEGRAM BOT TOKENS
    # --------------------------------------------------------

    $result = [regex]::Replace(
        $result,
        '(?i)(telegram[_-]?bot[_-]?token\s*[:=]\s*)[A-Za-z0-9:_-]+',
        '$1[REDACTED]'
    )

    # --------------------------------------------------------
    # 8. DATABASE URL PASSWORDS
    # --------------------------------------------------------

    $result = [regex]::Replace(
        $result,
        '(?i)(://[^:/\s]+:)[^@\s]+(@)',
        '$1[REDACTED]$2'
    )

    return $result
}

# ------------------------------------------------------------
# GET INCLUDED FILES
# ------------------------------------------------------------

Write-Host "Scanning dashboard files..." -ForegroundColor Yellow

$Files = Get-ChildItem `
    -LiteralPath $Root `
    -Recurse `
    -File `
    -Force |
    Where-Object {
        -not (Is-ExcludedPath $_.FullName)
    } |
    Sort-Object FullName

Write-Host "Included files: $($Files.Count)" -ForegroundColor Green
Write-Host ""

# ------------------------------------------------------------
# CREATE TREE
# ------------------------------------------------------------

$TreeBuilder = New-Object System.Text.StringBuilder

[void]$TreeBuilder.AppendLine("MJONAI DASHBOARD PROJECT TREE")
[void]$TreeBuilder.AppendLine("=============================")
[void]$TreeBuilder.AppendLine("")
[void]$TreeBuilder.AppendLine("ROOT: D:\MJONAI\mjonai-dashboard")
[void]$TreeBuilder.AppendLine("")
[void]$TreeBuilder.AppendLine("Excluded generated/cache directories:")
[void]$TreeBuilder.AppendLine("  .git")
[void]$TreeBuilder.AppendLine("  .pytest_cache")
[void]$TreeBuilder.AppendLine("  __pycache__")
[void]$TreeBuilder.AppendLine("  node_modules")
[void]$TreeBuilder.AppendLine("  dist")
[void]$TreeBuilder.AppendLine("  build")
[void]$TreeBuilder.AppendLine("  .next")
[void]$TreeBuilder.AppendLine("  coverage")
[void]$TreeBuilder.AppendLine("  virtual environments")
[void]$TreeBuilder.AppendLine("")
[void]$TreeBuilder.AppendLine("D:\MJONAI\mjonai-dashboard\")

function Add-Tree {
    param(
        [string]$Path,
        [string]$Prefix
    )

    $children = Get-ChildItem -LiteralPath $Path -Force |
        Where-Object {

            if ($_.PSIsContainer) {
                return -not (
                    $ExcludedDirectories -contains $_.Name
                )
            }

            return -not (
                $ExcludedFiles -contains $_.Name
            )
        } |
        Sort-Object `
            @{Expression = {
                if ($_.PSIsContainer) {
                    0
                }
                else {
                    1
                }
            }}, `
            Name

    for ($i = 0; $i -lt $children.Count; $i++) {

        $child = $children[$i]

        $isLast = ($i -eq ($children.Count - 1))

        if ($isLast) {
            $Branch = "\-- "
            $NextPrefix = "$Prefix    "
        }
        else {
            $Branch = "|-- "
            $NextPrefix = "$Prefix|   "
        }

        if ($child.PSIsContainer) {

            [void]$TreeBuilder.AppendLine(
                "$Prefix$Branch$($child.Name)\"
            )

            Add-Tree `
                -Path $child.FullName `
                -Prefix $NextPrefix
        }
        else {

            [void]$TreeBuilder.AppendLine(
                "$Prefix$Branch$($child.Name) [$($child.Length) bytes]"
            )
        }
    }
}

Add-Tree -Path $Root -Prefix ""

# ------------------------------------------------------------
# CREATE SNAPSHOT
# ------------------------------------------------------------

Write-Host "Creating full dashboard snapshot..." -ForegroundColor Yellow

$SnapshotBuilder = New-Object System.Text.StringBuilder

[void]$SnapshotBuilder.AppendLine(
    "MJONAI DASHBOARD FULL PROJECT SNAPSHOT"
)

[void]$SnapshotBuilder.AppendLine(
    "======================================"
)

[void]$SnapshotBuilder.AppendLine("")

[void]$SnapshotBuilder.AppendLine(
    "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
)

[void]$SnapshotBuilder.AppendLine(
    "Root: $Root"
)

[void]$SnapshotBuilder.AppendLine(
    "Files included: $($Files.Count)"
)

[void]$SnapshotBuilder.AppendLine("")

[void]$SnapshotBuilder.AppendLine(
    "SECURITY NOTICE:"
)

[void]$SnapshotBuilder.AppendLine(
    "Secrets, tokens, passwords, private keys and credential values are REDACTED."
)

[void]$SnapshotBuilder.AppendLine("")

# ------------------------------------------------------------
# TREE
# ------------------------------------------------------------

[void]$SnapshotBuilder.AppendLine(
    "============================================================"
)

[void]$SnapshotBuilder.AppendLine(
    "PROJECT TREE"
)

[void]$SnapshotBuilder.AppendLine(
    "============================================================"
)

[void]$SnapshotBuilder.AppendLine("")

[void]$SnapshotBuilder.Append(
    $TreeBuilder.ToString()
)

[void]$SnapshotBuilder.AppendLine("")

# ------------------------------------------------------------
# FILE CONTENT
# ------------------------------------------------------------

[void]$SnapshotBuilder.AppendLine(
    "============================================================"
)

[void]$SnapshotBuilder.AppendLine(
    "FILE CONTENT"
)

[void]$SnapshotBuilder.AppendLine(
    "============================================================"
)

[void]$SnapshotBuilder.AppendLine("")

$count = 0

foreach ($file in $Files) {

    $count++

    $relativePath = $file.FullName.Substring(
        $Root.Length
    ).TrimStart('\')

    Write-Progress `
        -Activity "Creating dashboard snapshot" `
        -Status "$count / $($Files.Count): $relativePath" `
        -PercentComplete (($count / $Files.Count) * 100)

    [void]$SnapshotBuilder.AppendLine("")

    [void]$SnapshotBuilder.AppendLine(
        "################################################################"
    )

    [void]$SnapshotBuilder.AppendLine(
        "FILE: $relativePath"
    )

    [void]$SnapshotBuilder.AppendLine(
        "SIZE: $($file.Length) bytes"
    )

    [void]$SnapshotBuilder.AppendLine(
        "################################################################"
    )

    [void]$SnapshotBuilder.AppendLine("")

    try {

        # --------------------------------------------------------
        # BINARY DETECTION
        # --------------------------------------------------------

        $bytes = [System.IO.File]::ReadAllBytes(
            $file.FullName
        )

        $isBinary = $false

        $checkLength = [Math]::Min(
            $bytes.Length,
            4096
        )

        for ($i = 0; $i -lt $checkLength; $i++) {

            if ($bytes[$i] -eq 0) {
                $isBinary = $true
                break
            }
        }

        if ($isBinary) {

            [void]$SnapshotBuilder.AppendLine(
                "[BINARY FILE - CONTENT NOT INCLUDED]"
            )

            continue
        }

        # --------------------------------------------------------
        # READ UTF-8 TEXT
        # --------------------------------------------------------

        $content = [System.IO.File]::ReadAllText(
            $file.FullName,
            [System.Text.Encoding]::UTF8
        )

        # --------------------------------------------------------
        # REDACT SECRETS
        # --------------------------------------------------------

        $redactedContent = Redact-Secrets `
            -Text $content

        [void]$SnapshotBuilder.Append(
            $redactedContent
        )

        if (-not $redactedContent.EndsWith("`n")) {
            [void]$SnapshotBuilder.AppendLine("")
        }
    }
    catch {

        [void]$SnapshotBuilder.AppendLine(
            "[UNABLE TO READ FILE: $($_.Exception.Message)]"
        )
    }
}

Write-Progress `
    -Activity "Creating dashboard snapshot" `
    -Completed

# ------------------------------------------------------------
# WRITE SNAPSHOT
# ------------------------------------------------------------

[System.IO.File]::WriteAllText(
    $SnapshotFile,
    $SnapshotBuilder.ToString(),
    [System.Text.UTF8Encoding]::new($false)
)

# ------------------------------------------------------------
# FINAL REPORT
# ------------------------------------------------------------

$SnapshotSize = (
    Get-Item -LiteralPath $SnapshotFile
).Length

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "MJONAI DASHBOARD SNAPSHOT COMPLETE" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Files included : $($Files.Count)"
Write-Host "Snapshot       : $SnapshotFile"
Write-Host "Snapshot size  : $([math]::Round($SnapshotSize / 1MB, 2)) MB"
Write-Host ""
Write-Host "Tree + file contents are in ONE file." -ForegroundColor Green
Write-Host "Secrets were REDACTED." -ForegroundColor Green
Write-Host ""