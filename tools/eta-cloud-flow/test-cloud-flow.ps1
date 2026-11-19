$ErrorActionPreference = 'Stop'
$root = 'F:\eta\06-环境运维工具\eta-cloud-flow'
$files = @(
    (Join-Path $root 'eta-cloud-flow.ps1'),
    (Join-Path $root 'sign-release.ps1'),
    'F:\eta\06-环境运维工具\eta-auto-delivery\eta-auto-push.ps1'
)
foreach ($file in $files) {
    $tokens = $null
    $errors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($file, [ref]$tokens, [ref]$errors)
    if ($errors.Count -gt 0) { throw "PowerShell syntax failed for ${file}: $($errors[0].Message)" }
    Write-Host "SYNTAX_OK $file"
}
foreach ($script in @('cloud-build.sh','cloud-source.sh')) {
    & wsl.exe -d Eta-Test-20261112 -u eta-test -- bash -n "/mnt/f/eta/06-环境运维工具/eta-cloud-flow/$script"
    if ($LASTEXITCODE -ne 0) { throw "Bash syntax failed for $script." }
    Write-Host "SYNTAX_OK $script"
}

$planText = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'eta-cloud-flow.ps1') `
    -SourceRepo 'F:\eta\projects\eta-night-20261118\worktree' `
    -Ref 'bd557bbb9ccb51d52b75b297a0e921d3f8afe0f2' -Mode compile -CheckOnly
if ($LASTEXITCODE -ne 0) { throw 'Local CheckOnly plan failed.' }
$plan = ($planText | Out-String | ConvertFrom-Json)
if ($plan.commit -ne 'bd557bbb9ccb51d52b75b297a0e921d3f8afe0f2' -or $plan.push -or $plan.install) {
    throw 'CheckOnly plan contains an unexpected source or side effect.'
}
Write-Host "PLAN_OK $($plan.commit) $($plan.mode)"

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'F:\eta\06-环境运维工具\eta-auto-delivery\eta-auto-push.ps1' -CheckOnly
if ($LASTEXITCODE -ne 0) { throw 'Existing auto-delivery CheckOnly guard failed.' }
Write-Host 'AUTO_DELIVERY_CHECK_ONLY_OK (no build, no push)'
