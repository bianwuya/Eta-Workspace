#Requires -Version 7.0
# Export an allowlisted, secret-scanned workspace rules/skills repository. No app source or private assets.
# Run with pwsh, not Windows PowerShell 5.1: UTF-8 native output is a release gate.
[CmdletBinding()]
param(
    [switch]$Publish,
    [switch]$CheckOnly,
    [string]$Message = 'chore(workspace): sync agent rules, skills and delivery tools'
)
$ErrorActionPreference = 'Stop'
# Git emits allowlisted paths as UTF-8. Without this, a Chinese system codepage
# turns valid staged names into mojibake and the safety gate rejects them.
$utf8 = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8
$sourceRoot = 'F:\eta'
$repo = 'F:\eta\projects\eta-workspace-sync\repository'
$manifestPath = Join-Path $PSScriptRoot 'workspace-manifest.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$entries = [System.Collections.Generic.List[object]]::new()
$allowedDest = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
[void]$allowedDest.Add('.gitignore')
[void]$allowedDest.Add('SYNC-INFO.md')
[void]$allowedDest.Add('SYNC-MANIFEST.json')

function Add-SyncEntry([string]$Source, [string]$Destination) {
    $full = Join-Path $sourceRoot $Source
    if (-not (Test-Path -LiteralPath $full -PathType Leaf)) { throw "Allowlisted source is missing: $Source" }
    $item = Get-Item -LiteralPath $full
    if ($item.Length -gt $manifest.maxFileBytes) { throw "File exceeds sync size limit: $Source" }
    $normalized = $Destination.Replace('\','/').TrimStart('/')
    if ($normalized.Contains('..') -or [IO.Path]::IsPathRooted($normalized)) { throw "Invalid destination: $Destination" }
    if ($normalized -match '(?i)(^|/)(keystore|phone-data|private-data|\.env|__pycache__)(/|$)|\.(jks|p12|pfx|pem|key|sqlite|db|jsonl|apk|pyc)$') {
        throw "Sensitive or binary file blocked: $normalized"
    }
    $text = [IO.File]::ReadAllText($item.FullName)
    if ($text -match '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----|github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,}') {
        throw "Credential-like content blocked in $Source"
    }
    $hash = (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $entries.Add([pscustomobject]@{ source = $Source; destination = $normalized; fullSource = $item.FullName; bytes = $item.Length; sha256 = $hash })
    [void]$allowedDest.Add($normalized)
}

function Get-RelativePath([string]$Base, [string]$FullName) {
    $normalizedFull = $FullName.Replace('/', '\')
    $prefix = $Base.Replace('/', '\').TrimEnd('\') + '\'
    if (-not $normalizedFull.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "File escapes the allowlisted directory: $FullName"
    }
    return $normalizedFull.Substring($prefix.Length)
}

foreach ($file in $manifest.files) { Add-SyncEntry $file.source $file.destination }
foreach ($directory in $manifest.directories) {
    $base = Join-Path $sourceRoot $directory.source
    if (-not (Test-Path -LiteralPath $base -PathType Container)) { throw "Allowlisted directory is missing: $($directory.source)" }
    $extensions = @($directory.extensions | ForEach-Object { $_.ToLowerInvariant() })
    $files = Get-ChildItem -LiteralPath $base -Recurse -File | Where-Object {
        $relative = Get-RelativePath $base $_.FullName
        $segments = $relative -split '[\\/]'
        $extensions -contains $_.Extension.ToLowerInvariant() -and
            -not ($segments | Where-Object { $manifest.excludedDirectories -contains $_ })
    }
    foreach ($file in $files) {
        $relative = Get-RelativePath $base $file.FullName.Replace('\','/')
        Add-SyncEntry "$($directory.source)/$relative" "$($directory.destination)/$relative"
    }
}
$entries = @($entries | Sort-Object destination -Unique)
if ($entries.Count -eq 0) { throw 'The sync allowlist produced no files.' }
$summary = [ordered]@{
    files = $entries.Count
    totalBytes = ($entries | Measure-Object bytes -Sum).Sum
    repository = $manifest.repositoryUrl
    branch = $manifest.branch
    publish = [bool]$Publish
}
if ($CheckOnly) {
    $summary | ConvertTo-Json
    exit 0
}

if (Test-Path -LiteralPath (Join-Path $repo '.git')) {
    & git -C $repo show-ref --verify --quiet "refs/heads/$($manifest.branch)"
    $hasCommit = $LASTEXITCODE -eq 0
    $syncStatus = @(& git -C $repo status --porcelain --untracked-files=normal)
    # A reviewed first export is necessarily uncommitted before its initial commit.
    # Later exports still require a clean repository; the staged allowlist below
    # rejects any unexpected file even during this initial publish.
    if ($hasCommit -and $syncStatus.Count -ne 0) {
        throw 'Sync repository has uncommitted changes; review them before exporting again.'
    }
} else {
    New-Item -ItemType Directory -Path $repo -Force | Out-Null
    & git -C $repo init -b $manifest.branch --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Unable to initialize the workspace sync repository.' }
}
if ((git -C $repo branch --show-current) -ne $manifest.branch) { throw 'Sync repository is on an unexpected branch.' }

foreach ($entry in $entries) {
    $destination = Join-Path $repo $entry.destination
    $parent = Split-Path -Parent $destination
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    Copy-Item -LiteralPath $entry.fullSource -Destination $destination -Force
}
@(
    '__pycache__/', '.pytest_cache/', 'node_modules/', '*.pyc', '*.apk', '*.jks', '*.db', '*.jsonl', '.env'
) | Set-Content -LiteralPath (Join-Path $repo '.gitignore') -Encoding ascii
@(
    '# Eta Workspace Agent Sync',
    '',
    'Allowlisted agent rules, project skills and delivery tools exported from the Eta workspace.',
    'No keystore, credentials, accounts, phone backups, private logs, APKs or unreviewed WIP are included.',
    "Source manifest: tools/eta-workspace-sync/workspace-manifest.json. Branch: $($manifest.branch).",
    '',
    'Clone: git clone --branch sync --single-branch https://github.com/bianwuya/Eta-Workspace.git',
    'Update: git -C Eta-Workspace pull --ff-only origin sync',
    'Usage and boundaries: tools/eta-workspace-sync/README.md.'
) | Set-Content -LiteralPath (Join-Path $repo 'SYNC-INFO.md') -Encoding utf8
$publicManifest = [ordered]@{
    version = $manifest.version
    source = 'Eta workspace allowlist'
    files = @($entries | ForEach-Object { [ordered]@{ source = $_.source; destination = $_.destination; bytes = $_.bytes; sha256 = $_.sha256 } })
}
$publicManifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $repo 'SYNC-MANIFEST.json') -Encoding utf8

& git -C $repo diff --check
if ($LASTEXITCODE -ne 0) { throw 'Exported content failed git diff --check.' }
if (-not $Publish) {
    Write-Host "WORKSPACE_EXPORTED: $repo ($($entries.Count) files; no commit or push)"
    exit 0
}
& git -C $repo add -- .
if ($LASTEXITCODE -ne 0) { throw 'Unable to stage the isolated sync repository.' }
$staged = @(& git -C $repo -c core.quotepath=false diff --cached --name-only)
$unexpected = @($staged | Where-Object { -not $allowedDest.Contains($_) })
if ($unexpected.Count -gt 0) { throw "Unexpected files in sync repository: $($unexpected -join ', ')" }
$tracked = @(& git -C $repo -c core.quotepath=false ls-files)
$stale = @($tracked | Where-Object { -not $allowedDest.Contains($_) })
if ($stale.Count -gt 0) { throw "Stale tracked files require explicit review: $($stale -join ', ')" }

$origin = [string](& git -C $repo remote get-url origin 2>$null)
if (-not $origin) {
    & git -C $repo remote add origin $manifest.repositoryUrl
} elseif ($origin.Trim() -ne $manifest.repositoryUrl) {
    throw 'Workspace sync origin does not match the approved repository.'
}
if (@(& git -C $repo -c core.quotepath=false diff --cached --name-only).Count -eq 0) {
    $head = (& git -C $repo rev-parse HEAD).Trim()
    Write-Host "WORKSPACE_SYNC_NO_CHANGES: $head"
} else {
    & git -C $repo commit -m $Message
    if ($LASTEXITCODE -ne 0) { throw 'Workspace sync commit failed.' }
    $head = (& git -C $repo rev-parse HEAD).Trim()
}
$env:GIT_TERMINAL_PROMPT = '0'
& git -C $repo -c credential.helper= -c credential.helper=manager -c credential.interactive=never push origin "HEAD:refs/heads/$($manifest.branch)"
if ($LASTEXITCODE -ne 0) { throw 'Workspace sync push failed; local commit is preserved.' }
$remoteLine = & git -C $repo -c credential.helper= -c credential.helper=manager -c credential.interactive=never ls-remote --heads origin "refs/heads/$($manifest.branch)"
if ($LASTEXITCODE -ne 0 -or -not ($remoteLine -match "^$head\s")) { throw 'Workspace sync remote SHA readback failed.' }
$receiptDir = 'F:\eta\07-构建与运行日志\eta-workspace-sync'
New-Item -ItemType Directory -Path $receiptDir -Force | Out-Null
$receipt = [ordered]@{ status = 'pushed'; commit = $head; files = $entries.Count; branch = $manifest.branch; repository = $manifest.repositoryUrl; verifiedAt = (Get-Date -Format o) }
$receipt | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $receiptDir "receipt-$($head.Substring(0,12)).json") -Encoding utf8
Write-Host "WORKSPACE_SYNC_VERIFIED: $head $($manifest.branch) ($($entries.Count) files)"
