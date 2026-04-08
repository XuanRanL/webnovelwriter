param(
    [ValidateSet("smoke", "full")]
    [string]$Mode = "smoke",
    [string]$ProjectRoot = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
} else {
    $ProjectRoot = (Resolve-Path $ProjectRoot).Path
}

Set-Location $ProjectRoot

$tmpRoot = Join-Path $ProjectRoot ".tmp\pytest-runtime"
New-Item -ItemType Directory -Path $tmpRoot -Force | Out-Null

$env:TMP = $tmpRoot
$env:TEMP = $tmpRoot
$env:PYTEST_TMPROOT = $tmpRoot
$env:PYTHONPATH = "webnovel-writer/scripts"

$runId = Get-Date -Format "yyyyMMdd_HHmmssfff"
$coverageRoot = Join-Path $env:LOCALAPPDATA "Temp\webnovel-writer-pytest-coverage"
New-Item -ItemType Directory -Path $coverageRoot -Force | Out-Null
$env:COVERAGE_FILE = (Join-Path $coverageRoot (".coverage-" + $Mode + "-" + $runId))

Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "TMP/TEMP: $tmpRoot"
Write-Host "Mode: $Mode"

if ($Mode -eq "smoke") {
    python -m pytest -q `
        webnovel-writer/scripts/data_modules/tests/test_extract_chapter_context.py `
        webnovel-writer/scripts/data_modules/tests/test_rag_adapter.py `
        --no-cov `
        -p no:tmpdir `
        -p no:cacheprovider
    exit $LASTEXITCODE
}

python -m pytest -q `
    webnovel-writer/scripts/data_modules/tests `
    -p no:tmpdir `
    -p no:cacheprovider
exit $LASTEXITCODE
