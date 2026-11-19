#Requires -Version 7.0
# Eta verified local-build -> GitHub feature-branch push. No automatic commit or remote stable-branch writes.
[CmdletBinding()]
param(
    [string]$RepoPath = 'F:\eta\projects\eta-night-20261118\worktree',
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
$target = [IO.Path]::GetFullPath('F:\eta\projects\eta-night-20261118\worktree').TrimEnd('\')
$repo = [IO.Path]::GetFullPath($RepoPath).TrimEnd('\')
if (-not [string]::Equals($repo, $target, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Only the approved isolated Eta night worktree is enabled. Not this repository."
}
function Invoke-EtaGit([string[]]$GitArgs) {
    $output = & git -C $repo @GitArgs
    if ($LASTEXITCODE -ne 0) { throw "Git command failed: $($GitArgs[0])" }
    return $output
}
$branch = [string](Invoke-EtaGit @('branch','--show-current'))
$branch = $branch.Trim()
if ($branch -ne 'night/v344-to-main-20261118') { throw "Refusing branch '$branch'; never auto-push main/local." }
$head = [string](Invoke-EtaGit @('rev-parse','HEAD'))
$head = $head.Trim()
if (@(Invoke-EtaGit @('status','--porcelain','--untracked-files=normal')).Count -ne 0) {
    throw 'Uncommitted/staged/untracked files exist. Preserve WIP; skip build/push.'
}
$origin = [string](Invoke-EtaGit @('remote','get-url','--push','origin'))
$origin = $origin.Trim()
if ($origin -notmatch '^(https://github\.com/bianwuya/Eta(\.git)?|git@github\.com:bianwuya/Eta(\.git)?)$') {
    throw 'Origin is not the approved bianwuya/Eta GitHub repository or contains credentials.'
}
$files = @(Invoke-EtaGit @('ls-tree','-r','--name-only','HEAD'))
$forbidden = @($files | Where-Object { $_ -match '(?i)(^|/)(keystore|phone-data|private-data|\.env)(/|$)|\.(jks|p12|pfx|pem|key|sqlite|db|jsonl)$' })
if ($forbidden.Count -gt 0) { throw "Potential private files committed ($($forbidden.Count)); review before pushing." }
Write-Host "Eta auto-delivery HEAD=$head branch=$branch clean=$true remote=bianwuya/Eta"
if ($CheckOnly) {
    Write-Host 'CHECK_ONLY: no build or push occurred.'
    exit 0
}
$root = 'F:\eta\projects\eta-night-20261118'
$logDir = 'F:\eta\07-构建与运行日志\eta-auto-delivery'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$lock = Join-Path $logDir 'active.lock'
if (Test-Path -LiteralPath $lock) { throw "Another delivery is active (or stale lock): $lock" }
New-Item -ItemType Directory -Path $lock -ErrorAction Stop | Out-Null
$receipt = Join-Path $logDir "receipt-$($head.Substring(0,12)).txt"
$started = Get-Date -Format o
try {
    @("START $started","HEAD $head","BRANCH $branch") | Set-Content -LiteralPath $receipt -Encoding utf8
    $runName = "autopush-$($head.Substring(0,12))"
    $runDir = Join-Path $logDir $runName
    Write-Host 'Linux: compile, tests, lint and unsigned assembly; Windows: original signing only...'
    & pwsh -NoProfile -File 'F:\eta\06-环境运维工具\eta-cloud-flow\eta-cloud-flow.ps1' `
        -SourceRepo $repo -Ref $head -Mode delivery -Name $runName -OutputRoot $logDir
    if ($LASTEXITCODE -ne 0) { throw 'Unified Linux build/sign flow failed; push blocked.' }
    $sdkBuildTools = 'F:\eta\05-本地构建工具链\android-sdk\build-tools\37.0.0\apksigner.bat'
    if (-not (Test-Path -LiteralPath $sdkBuildTools)) { throw 'Local apksigner unavailable; push blocked.' }
    $apkPaths = @{
        debug = Join-Path $runDir 'debug.apk'
        release = Join-Path $runDir 'release-original-signed.apk'
    }
    foreach ($variant in @('debug','release')) {
        $apk = Get-Item -LiteralPath $apkPaths[$variant]
        & $sdkBuildTools verify $apk.FullName
        if ($LASTEXITCODE -ne 0) { throw "$variant APK signature verification failed." }
        $hash = (Get-FileHash -LiteralPath $apk.FullName -Algorithm SHA256).Hash
        Add-Content -LiteralPath $receipt -Value ("APK {0} {1} sha256={2}" -f $variant,$apk.Length,$hash)
    }
    if ([string](Invoke-EtaGit @('rev-parse','HEAD')) -ne $head -or @(Invoke-EtaGit @('status','--porcelain','--untracked-files=normal')).Count -ne 0) {
        throw 'Source changed during APK build; push blocked.'
    }
    # No force, no tags, no local/main, no PR. Existing non-fast-forward protection is preserved.
    $env:GIT_TERMINAL_PROMPT='0'
    & git -C $repo -c credential.helper= -c credential.helper=manager -c credential.interactive=never push origin "HEAD:refs/heads/$branch"
    if ($LASTEXITCODE -ne 0) { throw 'GitHub push failed. Local commit is preserved.' }
    $remoteLine = & git -C $repo -c credential.helper= -c credential.helper=manager -c credential.interactive=never ls-remote --heads origin "refs/heads/$branch"
    if ($LASTEXITCODE -ne 0 -or -not ($remoteLine -match "^$head\s")) { throw 'GitHub ref readback did not match HEAD; push unverified.' }
    Add-Content -LiteralPath $receipt -Value ("PUSH_VERIFIED $head $(Get-Date -Format o)")
    Write-Host "PUSH_VERIFIED: bianwuya/Eta $branch $head"
} catch {
    Add-Content -LiteralPath $receipt -Value ("FAILED $(Get-Date -Format o): $($_.Exception.Message)")
    Write-Error $_.Exception.Message
    exit 1
} finally {
    Remove-Item -LiteralPath $lock -Recurse -Force -ErrorAction SilentlyContinue
}
