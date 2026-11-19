# Sign one Linux-built unsigned release with the existing original certificate. No Gradle or installation.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$UnsignedApk,
    [Parameter(Mandatory=$true)][string]$SignedApk,
    [Parameter(Mandatory=$true)][string]$ExpectedVersionName,
    [string]$ExpectedSigner = 'a7a92cca03f7d7390ab74001c97efbfe4ff4289b0dc4ffa21d6ebc3cee1c81a8'
)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$unsigned = (Get-Item -LiteralPath $UnsignedApk).FullName
$signed = [IO.Path]::GetFullPath($SignedApk)
if ($signed -ieq $unsigned) { throw 'Signed output must differ from the unsigned input.' }
if (Test-Path -LiteralPath $signed) { throw 'Signed output already exists; refusing to overwrite it.' }
$parent = Split-Path -Parent $signed
if (-not (Test-Path -LiteralPath $parent -PathType Container)) { throw 'Signed output parent directory does not exist.' }
$temp = "$signed.unverified"
if (Test-Path -LiteralPath $temp) { throw 'An unverified output already exists; inspect it before retrying.' }

. 'F:\eta\eta-signing.ps1'
$signer = 'F:\eta\05-本地构建工具链\android-sdk\build-tools\37.0.0\apksigner.bat'
$aapt2 = 'F:\eta\05-本地构建工具链\android-sdk\build-tools\37.0.0\aapt2.exe'
if (-not (Test-Path -LiteralPath $signer -PathType Leaf)) { throw 'Local apksigner is unavailable.' }
if (-not (Test-Path -LiteralPath $aapt2 -PathType Leaf)) { throw 'Local aapt2 is unavailable.' }

$signArgs = @(
    'sign', '--ks', $env:ETA_RELEASE_STORE_FILE,
    '--ks-key-alias', $env:ETA_RELEASE_KEY_ALIAS,
    '--ks-pass', 'env:ETA_RELEASE_STORE_PASSWORD',
    '--key-pass', 'env:ETA_RELEASE_KEY_PASSWORD',
    '--v1-signing-enabled', 'false', '--v2-signing-enabled', 'true',
    '--v3-signing-enabled', 'false', '--v4-signing-enabled', 'false',
    '--out', $temp, $unsigned
)
& $signer @signArgs
if ($LASTEXITCODE -ne 0) { throw 'apksigner signing failed; no signed APK was delivered.' }

$verification = (& $signer verify --verbose --print-certs $temp) -join "`n"
if ($LASTEXITCODE -ne 0 -or $verification -notmatch '(?m)^Verified using v2 scheme [^\r\n]+: true\s*$') {
    throw 'APK v2 signature verification failed; inspect the .unverified file.'
}
$certs = [regex]::Matches($verification, '(?im)^(?:V2 Signer: certificate|Signer #[0-9]+ certificate) SHA-256 digest: ([0-9a-f]{64})[ \t]*\r?$')
if ($certs.Count -ne 1 -or $certs[0].Groups[1].Value -ine $ExpectedSigner) {
    throw 'Certificate does not match the installed Eta original signer.'
}
$badging = (& $aapt2 dump badging $temp) -join "`n"
if ($LASTEXITCODE -ne 0 -or -not $badging.Contains("package: name='io.github.mangi.eta' ") -or
    -not $badging.Contains("versionName='$ExpectedVersionName'")) {
    throw 'APK package name or versionName does not match the requested source commit.'
}
$inputHash = (Get-FileHash -LiteralPath $unsigned -Algorithm SHA256).Hash.ToLowerInvariant()
$hash = (Get-FileHash -LiteralPath $temp -Algorithm SHA256).Hash.ToLowerInvariant()
Move-Item -LiteralPath $temp -Destination $signed -ErrorAction Stop
"$hash  $([IO.Path]::GetFileName($signed))" | Out-File -LiteralPath "$signed.sha256" -Encoding ascii -NoClobber
@(
    "INPUT_SHA256 $inputHash",
    "SIGNED_SHA256 $hash",
    "SIGNER_SHA256 $ExpectedSigner",
    "VERSION_NAME $ExpectedVersionName"
) | Set-Content -LiteralPath "$signed.signing-receipt.txt" -Encoding utf8
Write-Host "Verified original signer: $ExpectedSigner"
Write-Host "Signed APK: $signed"
Write-Host "SHA-256: $hash"
