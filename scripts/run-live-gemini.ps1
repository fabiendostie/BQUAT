param(
    [string]$SecretPath = "$env:LOCALAPPDATA\BAQT\secrets\gemini_api_key.xml",
    [string]$Model = "gemini-3-flash-preview",
    [string]$TestPath = "tests/test_integration_live_provider.py",
    [switch]$KeepRuns,
    [switch]$Lifecycle
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Test-Path $SecretPath)) {
    Write-Error "Secret file not found: $SecretPath"
    Write-Error "Create it with: Read-Host \"Enter GEMINI_API_KEY\" -AsSecureString | Export-Clixml $SecretPath"
    exit 1
}

$secret = Import-Clixml $SecretPath
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
try {
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

if ([string]::IsNullOrWhiteSpace($plain)) {
    Write-Error "Loaded GEMINI_API_KEY is empty."
    exit 1
}

$env:GEMINI_API_KEY = $plain
$env:BAQT_LIVE_PROVIDER = "gemini"
$env:BAQT_LIVE_MODEL = $Model
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
if ($KeepRuns) {
    $env:BAQT_LIVE_KEEP_RUNS = "1"
}
if ($Lifecycle) {
    $env:BAQT_LIVE_E2E = "1"
    $TestPath = "tests/test_integration_full_lifecycle_live.py"
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $repoRoot
try {
    python -m pytest $TestPath
    $exitCode = $LASTEXITCODE
} finally {
    Pop-Location
    Remove-Item Env:GEMINI_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:BAQT_LIVE_PROVIDER -ErrorAction SilentlyContinue
    Remove-Item Env:BAQT_LIVE_MODEL -ErrorAction SilentlyContinue
    Remove-Item Env:PYTHONIOENCODING -ErrorAction SilentlyContinue
    Remove-Item Env:PYTHONUTF8 -ErrorAction SilentlyContinue
    Remove-Item Env:BAQT_LIVE_KEEP_RUNS -ErrorAction SilentlyContinue
    Remove-Item Env:BAQT_LIVE_E2E -ErrorAction SilentlyContinue
}

exit $exitCode
