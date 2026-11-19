# Cloud/local commit -> review evidence -> Linux build -> Windows original signing. No push or installation.
#Requires -Version 7.0
[CmdletBinding()]
param(
    [string]$RepoUrl = 'https://github.com/bianwuya/Eta.git',
    [ValidateSet('Linux','WindowsArchive')][string]$CloudTransport = 'Linux',
    [string]$Branch,
    [string]$SourceRepo,
    [string]$Ref = 'HEAD',
    [ValidateSet('compile','test','assemble','delivery')][string]$Mode = 'compile',
    [string]$Name,
    [string]$OutputRoot = 'F:\eta\07-构建与运行日志\eta-cloud-flow',
    [string]$CompareRef,
    [switch]$UseCached,
    [switch]$Online,
    [switch]$SkipSign,
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
$env:GIT_TERMINAL_PROMPT = '0'

function ConvertTo-WslPath([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path)
    if ($full.Length -lt 3 -or $full[1] -ne ':') { throw "Only local drive paths are supported: $full" }
    $drive = $full.Substring(0,1).ToLowerInvariant()
    $rest = $full.Substring(2).Replace('\','/').TrimStart('/')
    return "/mnt/$drive/$rest"
}
function Invoke-EtaGit([string]$GitPath, [string[]]$GitArgs) {
    $output = & git -C $GitPath @GitArgs
    if ($LASTEXITCODE -ne 0) { throw "Git failed ($($GitArgs[0])) for $GitPath" }
    return $output
}
function Get-Sha256Text([string]$Text) {
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes($Text.ToLowerInvariant())
        return (($algorithm.ComputeHash($bytes) | ForEach-Object { $_.ToString('x2') }) -join '')
    } finally { $algorithm.Dispose() }
}

if ($SourceRepo -and $Branch) { throw 'Use either SourceRepo with Ref, or RepoUrl with Branch; not both.' }
if (-not $SourceRepo -and -not $Branch) { throw 'Branch is required for cloud mode.' }
if ($Ref.StartsWith('-') -or $Branch.StartsWith('-') -or $CompareRef.StartsWith('-')) { throw 'Refs must not start with a dash.' }
if ($Branch -and ($Branch -notmatch '^[A-Za-z0-9._/-]+$' -or $Branch.Contains('..') -or $Branch.Contains('@{'))) {
    throw 'Branch contains unsupported characters.'
}
if ($RepoUrl -notmatch '^(https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(\.git)?|git@github\.com:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(\.git)?)$') {
    throw 'RepoUrl must be a credential-free GitHub repository URL.'
}

$sourceIsLinux = $false
if ($SourceRepo) {
    $sourceGit = [IO.Path]::GetFullPath($SourceRepo).TrimEnd('\')
    $workspacePrefix = 'F:\eta\'
    if (-not $sourceGit.StartsWith($workspacePrefix,[StringComparison]::OrdinalIgnoreCase)) {
        throw 'SourceRepo must be inside F:\eta.'
    }
    [void](Invoke-EtaGit $sourceGit @('rev-parse','--git-dir'))
    $sourceIdentity = $sourceGit
    $commit = [string](Invoke-EtaGit $sourceGit @('rev-parse',"$Ref^{commit}"))
    $tree = [string](Invoke-EtaGit $sourceGit @('rev-parse',"$Ref^{tree}"))
    $sourceKind = 'local-commit'
    $sourceTransport = 'windows-archive'
} else {
    $sourceIdentity = $RepoUrl
    $Ref = "refs/heads/$Branch"
    if ($CloudTransport -eq 'Linux') {
        $sourceScript = Join-Path $PSScriptRoot 'cloud-source.sh'
        $sourceOutput = & wsl.exe -d Eta-Test-20261112 -u eta-test -- bash (ConvertTo-WslPath $sourceScript) `
            $RepoUrl $Branch $(if ($UseCached) { '1' } else { '0' })
        if ($LASTEXITCODE -ne 0) {
            throw 'Linux source fetch failed. For private sources requiring Windows credentials, explicitly use -CloudTransport WindowsArchive.'
        }
        $sourceInfo = ($sourceOutput | Out-String | ConvertFrom-Json)
        $commit = [string]$sourceInfo.commit
        $tree = [string]$sourceInfo.tree
        $sourceGit = [string]$sourceInfo.sourceGit
        $sourceIsLinux = $true
        $sourceTransport = 'linux-native'
        $sourceKind = $(if ($UseCached) { 'cloud-linux-cached' } else { 'cloud-linux-fetched' })
    } else {
        $cacheRoot = 'F:\eta\projects\eta-cloud-flow-cache'
        New-Item -ItemType Directory -Path $cacheRoot -Force | Out-Null
        $mirror = Join-Path $cacheRoot ((Get-Sha256Text $RepoUrl).Substring(0,12) + '.git')
        if (-not (Test-Path -LiteralPath $mirror)) {
            & git init --bare --quiet $mirror
            if ($LASTEXITCODE -ne 0) { throw 'Unable to initialize the cloud source mirror.' }
        }
        if (-not (Test-Path -LiteralPath (Join-Path $mirror 'HEAD') -PathType Leaf)) {
            throw 'Cloud cache path exists but is not a bare Git mirror.'
        }
        if (-not $UseCached) {
            & git -C $mirror fetch --no-tags $RepoUrl "+refs/heads/${Branch}:refs/heads/${Branch}"
            if ($LASTEXITCODE -ne 0) { throw 'Cloud fetch failed; existing source worktrees were not changed.' }
        }
        $sourceGit = $mirror
        $commit = [string](Invoke-EtaGit $sourceGit @('rev-parse',"$Ref^{commit}"))
        $tree = [string](Invoke-EtaGit $sourceGit @('rev-parse',"$Ref^{tree}"))
        $sourceTransport = 'windows-archive'
        $sourceKind = $(if ($UseCached) { 'cloud-cached' } else { 'cloud-fetched' })
    }
}
$commit = $commit.Trim().ToLowerInvariant()
$tree = $tree.Trim().ToLowerInvariant()
if ($commit -notmatch '^[0-9a-f]{40}$' -or $tree -notmatch '^[0-9a-f]{40}$') {
    throw 'Unable to resolve full source commit and tree SHA.'
}

$plan = [ordered]@{
    sourceKind = $sourceKind
    sourceIdentity = $sourceIdentity
    sourceGit = $sourceGit
    requestedRef = $Ref
    commit = $commit
    tree = $tree
    sourceTransport = $sourceTransport
    mode = $Mode
    connectivity = $(if ($Online) { 'online' } else { 'offline' })
    sign = $(if ($Mode -in @('assemble','delivery') -and -not $SkipSign) { 'windows-original-only' } else { 'none' })
    push = $false
    install = $false
}
if ($CheckOnly) {
    $plan | ConvertTo-Json -Depth 3
    exit 0
}

if (-not $Name) { $Name = "$Mode-$($commit.Substring(0,12))-$(Get-Date -Format 'yyyyMMdd-HHmmss')" }
if ($Name -notmatch '^[A-Za-z0-9._-]+$') { throw 'Name may contain only letters, digits, dot, underscore and hyphen.' }
$outputFull = [IO.Path]::GetFullPath($OutputRoot).TrimEnd('\')
$allowedOutput = 'F:\eta\07-构建与运行日志'
if (-not $outputFull.StartsWith($allowedOutput,[StringComparison]::OrdinalIgnoreCase)) {
    throw 'OutputRoot must stay inside F:\eta\07-构建与运行日志.'
}
$runDir = Join-Path $outputFull $Name
if (Test-Path -LiteralPath $runDir) { throw "Run directory already exists: $runDir" }
New-Item -ItemType Directory -Path $runDir -ErrorAction Stop | Out-Null
$started = Get-Date
try {
    $plan | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $runDir 'source.json') -Encoding utf8
    if ($CompareRef) {
        if ($sourceIsLinux) {
            $compare = (& wsl.exe -d Eta-Test-20261112 -u eta-test -- git -C $sourceGit rev-parse "$CompareRef^{commit}").Trim()
            & wsl.exe -d Eta-Test-20261112 -u eta-test -- git -C $sourceGit diff --name-status $compare $commit |
                Set-Content -LiteralPath (Join-Path $runDir 'review-files.txt') -Encoding utf8
            if ($LASTEXITCODE -ne 0) { throw 'Unable to generate the Linux review file list.' }
            & wsl.exe -d Eta-Test-20261112 -u eta-test -- git -C $sourceGit diff --no-binary $compare $commit |
                Set-Content -LiteralPath (Join-Path $runDir 'review.diff') -Encoding utf8
            if ($LASTEXITCODE -ne 0) { throw 'Unable to generate the Linux review diff.' }
        } else {
            $compare = ([string](Invoke-EtaGit $sourceGit @('rev-parse',"$CompareRef^{commit}"))).Trim()
            & git -C $sourceGit diff --name-status $compare $commit | Set-Content -LiteralPath (Join-Path $runDir 'review-files.txt') -Encoding utf8
            if ($LASTEXITCODE -ne 0) { throw 'Unable to generate the review file list.' }
            & git -C $sourceGit diff --no-binary $compare $commit | Set-Content -LiteralPath (Join-Path $runDir 'review.diff') -Encoding utf8
            if ($LASTEXITCODE -ne 0) { throw 'Unable to generate the review diff.' }
        }
    }

    $buildScript = Join-Path $PSScriptRoot 'cloud-build.sh'
    $buildPrefix = @('-d','Eta-Test-20261112','-u','eta-test','--','bash',(ConvertTo-WslPath $buildScript))
    if ($sourceIsLinux) {
        $buildArgs = $buildPrefix + @(
            'wslgit',$sourceGit,$commit,$tree,$Name,$Mode,
            $(if ($Online) { 'online' } else { 'offline' }),(ConvertTo-WslPath $runDir)
        )
    } else {
        $archive = Join-Path $runDir 'source.tar'
        & git -C $sourceGit archive --format=tar --output=$archive $commit
        if ($LASTEXITCODE -ne 0) { throw 'Unable to archive the exact source commit.' }
        $archiveHash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
        Set-Content -LiteralPath (Join-Path $runDir 'source-archive.sha256') -Value "$archiveHash  source.tar" -Encoding ascii
        $buildArgs = $buildPrefix + @(
            'archive',(ConvertTo-WslPath $archive),$commit,$tree,$archiveHash,$Name,$Mode,
            $(if ($Online) { 'online' } else { 'offline' }),(ConvertTo-WslPath $runDir)
        )
    }
    & wsl.exe @buildArgs
    if ($LASTEXITCODE -ne 0) { throw 'Linux source validation or Gradle build failed; signing is blocked.' }

    $signedPath = ''
    if ($Mode -in @('assemble','delivery')) {
        $debug = Join-Path $runDir 'debug.apk'
        $unsigned = Join-Path $runDir 'release-unsigned.apk'
        if (-not (Test-Path -LiteralPath $debug -PathType Leaf) -or -not (Test-Path -LiteralPath $unsigned -PathType Leaf)) {
            throw 'Linux build passed but APK artifacts are missing.'
        }
        if (-not $SkipSign) {
            $signed = Join-Path $runDir 'release-original-signed.apk'
            $unsignedBadging = (& 'F:\eta\05-本地构建工具链\android-sdk\build-tools\37.0.0\aapt2.exe' dump badging $unsigned) -join "`n"
            $versionMatch = [regex]::Match($unsignedBadging, "(?m)^package:.*versionName='([^']+)'")
            if ($LASTEXITCODE -ne 0 -or -not $versionMatch.Success) { throw 'Unable to read the unsigned APK versionName.' }
            $expectedVersion = $versionMatch.Groups[1].Value
            if (-not $expectedVersion.EndsWith("+$commit", [StringComparison]::Ordinal)) {
                throw 'Unsigned APK versionName does not contain the exact source commit.'
            }
            & (Join-Path $PSScriptRoot 'sign-release.ps1') -UnsignedApk $unsigned -SignedApk $signed -ExpectedVersionName $expectedVersion
            $signedPath = $signed
        }
        . 'F:\eta\eta-env.ps1'
        & 'F:\eta\05-本地构建工具链\android-sdk\build-tools\37.0.0\apksigner.bat' verify $debug
        if ($LASTEXITCODE -ne 0) { throw 'Debug APK signature verification failed.' }
    }
    $duration = [int](Get-Content -LiteralPath (Join-Path $runDir 'duration-seconds') -Raw)
    @(
        "STATUS passed",
        "COMMIT $commit",
        "MODE $Mode",
        "BUILD_SECONDS $duration",
        "FLOW_SECONDS $([int]((Get-Date)-$started).TotalSeconds)",
        "SIGNED_RELEASE $signedPath",
        "PUSH false",
        "INSTALL false",
        "FINISHED $(Get-Date -Format o)"
    ) | Set-Content -LiteralPath (Join-Path $runDir 'flow-result.txt') -Encoding utf8
    Write-Host "FLOW_OK: $runDir"
    Write-Host "SOURCE: $commit | MODE: $Mode | BUILD_SECONDS: $duration"
    if ($signedPath) { Write-Host "SIGNED_RELEASE: $signedPath" }
} catch {
    @("STATUS failed","COMMIT $commit","ERROR $($_.Exception.Message)","FINISHED $(Get-Date -Format o)") |
        Set-Content -LiteralPath (Join-Path $runDir 'flow-result.txt') -Encoding utf8
    Write-Error $_.Exception.Message
    exit 1
}
