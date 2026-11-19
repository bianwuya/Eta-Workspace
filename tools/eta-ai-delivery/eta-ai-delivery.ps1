#Requires -Version 7.0
# AI task-level explicit-file commit -> exact-commit Linux delivery -> non-forced branch push.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RepoPath,
    [Parameter(Mandatory = $true)][string[]]$Files,
    [Parameter(Mandatory = $true)][string]$Message,
    [string]$RemoteName = 'github',
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
$utf8 = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8
$repo = [IO.Path]::GetFullPath($RepoPath).TrimEnd('\')
$allowedRoot = [IO.Path]::GetFullPath('F:\eta\projects').TrimEnd('\') + '\'
if (-not $repo.StartsWith($allowedRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'AI delivery requires an isolated repository below F:/eta/projects.'
}
if (-not (Test-Path -LiteralPath $repo -PathType Container)) { throw "Repository not found: $repo" }
if ([string]::IsNullOrWhiteSpace($Message) -or $Message.Length -gt 120) { throw 'A concise commit message is required.' }
if ($RemoteName -notmatch '^[A-Za-z0-9._-]+$') { throw 'Invalid remote name.' }
$env:GIT_TERMINAL_PROMPT = '0'

function Invoke-EtaGit([string[]]$GitArgs) {
    $output = & git -C $repo @GitArgs
    if ($LASTEXITCODE -ne 0) { throw "Git command failed: $($GitArgs[0])" }
    return $output
}

$top = [IO.Path]::GetFullPath([string](Invoke-EtaGit @('rev-parse', '--show-toplevel')).Trim()).TrimEnd('\')
if (-not $top.Equals($repo, [StringComparison]::OrdinalIgnoreCase)) { throw 'RepoPath must be the isolated Git worktree root.' }
$branch = [string](Invoke-EtaGit @('branch', '--show-current')).Trim()
if ($branch -notmatch '^(fix|feat|feature|ai|night|chore|docs)/[A-Za-z0-9._/-]+$' -or $branch -match '(^|/)(main|local|master)$') {
    throw "Refusing non-development branch '$branch'."
}
$origin = [string](Invoke-EtaGit @('remote', 'get-url', '--push', $RemoteName)).Trim()
if ($origin -notmatch '^(https://github\.com/bianwuya/Eta(\.git)?|git@github\.com:bianwuya/Eta(\.git)?)$') {
    throw "Remote '$RemoteName' is not the approved credential-free bianwuya/Eta repository."
}
if (@(Invoke-EtaGit @('diff', '--cached', '--name-only')).Count -ne 0) {
    throw 'Pre-staged changes exist. Review them separately; AI delivery stages only its explicit files.'
}

$relativeFiles = [System.Collections.Generic.List[string]]::new()
foreach ($file in ($Files | Sort-Object -Unique)) {
    if ([string]::IsNullOrWhiteSpace($file)) { throw 'Empty file path is not allowed.' }
    $full = if ([IO.Path]::IsPathRooted($file)) { [IO.Path]::GetFullPath($file) } else { [IO.Path]::GetFullPath((Join-Path $repo $file)) }
    if (-not $full.StartsWith($repo + '\', [StringComparison]::OrdinalIgnoreCase)) { throw "File escapes the worktree: $file" }
    if (-not (Test-Path -LiteralPath $full -PathType Leaf)) { throw "Explicit file is missing: $file" }
    $relative = [IO.Path]::GetRelativePath($repo, $full).Replace('\', '/')
    if ($relative -match '(?i)(^|/)(keystore|phone-data|private-data|\.env|__pycache__)(/|$)|\.(jks|p12|pfx|pem|key|sqlite|db|jsonl|apk|pyc)$') {
        throw "Sensitive or binary file blocked: $relative"
    }
    $text = [IO.File]::ReadAllText($full)
    if ($text.Contains("`0")) { throw "Binary file blocked: $relative" }
    if ($text -match '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----|github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,}') {
        throw "Credential-like content blocked: $relative"
    }
    $relativeFiles.Add($relative)
}
if ($relativeFiles.Count -eq 0) { throw 'No explicit files supplied.' }

if ($CheckOnly) {
    [ordered]@{
        status = 'check-only'
        repository = $repo
        branch = $branch
        remote = $RemoteName
        files = @($relativeFiles)
        commit = $false
        build = $false
        push = $false
    } | ConvertTo-Json -Depth 4
    exit 0
}

$logDir = 'F:\eta\07-构建与运行日志\eta-ai-delivery'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$lock = Join-Path $logDir 'active.lock'
if (Test-Path -LiteralPath $lock) { throw "Another AI delivery is active or stale: $lock" }
New-Item -ItemType Directory -Path $lock -ErrorAction Stop | Out-Null
$receipt = Join-Path $logDir ("receipt-{0}.txt" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
$started = Get-Date -Format o
try {
    @("START $started", "REPO $repo", "BRANCH $branch", "FILES $($relativeFiles -join ',')") | Set-Content -LiteralPath $receipt -Encoding utf8
    & git -C $repo --literal-pathspecs add -- @relativeFiles
    if ($LASTEXITCODE -ne 0) { throw 'Unable to stage the explicit AI files.' }
    $expected = @($relativeFiles | Sort-Object -Unique)
    $staged = @(Invoke-EtaGit @('-c', 'core.quotepath=false', 'diff', '--cached', '--name-only') | Sort-Object -Unique)
    if (Compare-Object $expected $staged) { throw 'Staged file set differs from the explicit AI file list.' }
    if ($staged.Count -eq 0) { throw 'The explicit files contain no changes to commit.' }
    & git -C $repo commit -m $Message
    if ($LASTEXITCODE -ne 0) { throw 'AI task commit failed.' }
    $head = [string](Invoke-EtaGit @('rev-parse', 'HEAD')).Trim()
    Add-Content -LiteralPath $receipt -Value "COMMIT $head"

    $runName = "ai-delivery-$($head.Substring(0, 12))"
    Write-Host "Linux exact-commit delivery: $head ($branch)"
    & pwsh -NoProfile -File 'F:\eta\06-环境运维工具\eta-cloud-flow\eta-cloud-flow.ps1' `
        -SourceRepo $repo -Ref $head -CloudTransport WindowsArchive -Mode delivery -Name $runName -OutputRoot $logDir
    if ($LASTEXITCODE -ne 0) { throw 'Linux build/test/lint or Windows signing failed; local commit preserved and push blocked.' }

    $runDir = Join-Path $logDir $runName
    $flow = Get-Content -LiteralPath (Join-Path $runDir 'flow-result.txt') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($flow.sourceCommit -ne $head) { throw 'Built source SHA does not match the AI task commit.' }
    $sdkBuildTools = 'F:\eta\05-本地构建工具链\android-sdk\build-tools\37.0.0\apksigner.bat'
    $env:JAVA_HOME = 'F:\eta\05-本地构建工具链\jdk\jdk-25.0.5.0.3'
    foreach ($variant in @('debug', 'release')) {
        $name = if ($variant -eq 'debug') { 'debug.apk' } else { 'release-original-signed.apk' }
        $apk = Get-Item -LiteralPath (Join-Path $runDir $name)
        & $sdkBuildTools verify $apk.FullName
        if ($LASTEXITCODE -ne 0) { throw "$variant APK signature verification failed; push blocked." }
        $hash = (Get-FileHash -LiteralPath $apk.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        Add-Content -LiteralPath $receipt -Value ("APK {0} {1} sha256={2}" -f $variant, $apk.Length, $hash)
    }
    if ([string](Invoke-EtaGit @('rev-parse', 'HEAD')).Trim() -ne $head) { throw 'HEAD changed during delivery; push blocked.' }
    if (@(Invoke-EtaGit @('diff', '--cached', '--name-only')).Count -ne 0) { throw 'Unexpected staged changes appeared during delivery.' }
    $selectedStatus = @(& git -C $repo --literal-pathspecs status --porcelain -- @relativeFiles)
    if ($LASTEXITCODE -ne 0 -or $selectedStatus.Count -ne 0) { throw 'An explicit source file changed after its commit; push blocked.' }

    & git -C $repo -c credential.interactive=never push $RemoteName "HEAD:refs/heads/$branch"
    if ($LASTEXITCODE -ne 0) { throw 'GitHub push failed; the verified local commit is preserved.' }
    $remoteLine = & git -C $repo -c credential.interactive=never ls-remote --heads $RemoteName "refs/heads/$branch"
    if ($LASTEXITCODE -ne 0 -or -not ($remoteLine -match "^$head\s")) { throw 'Remote SHA readback did not match the verified commit.' }
    Add-Content -LiteralPath $receipt -Value "PUSH_VERIFIED $head $(Get-Date -Format o)"
    Write-Host "AI_DELIVERY_VERIFIED: $head $branch"
    Write-Host "RECEIPT: $receipt"
} catch {
    Add-Content -LiteralPath $receipt -Value "FAILED $(Get-Date -Format o): $($_.Exception.Message)"
    throw
} finally {
    Remove-Item -LiteralPath $lock -Recurse -Force -ErrorAction SilentlyContinue
}
