param(
    [ValidateSet("smoke", "full")]
    [string]$Mode = "smoke",
    [string]$ProjectRoot = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path
} else {
    $ProjectRoot = (Resolve-Path $ProjectRoot).Path
}

Set-Location $ProjectRoot

$tmpRoot = Join-Path $ProjectRoot ".tmp\\pytest"
New-Item -ItemType Directory -Path $tmpRoot -Force | Out-Null

$env:TMP = $tmpRoot
$env:TEMP = $tmpRoot
$env:PYTHONPATH = ".claude/scripts"

$baseTemp = Join-Path $tmpRoot ("run-" + $Mode)

Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "TMP/TEMP: $tmpRoot"
Write-Host "Mode: $Mode"

if ($Mode -eq "smoke") {
    python -m pytest -q `
        .claude/scripts/data_modules/tests/test_extract_chapter_context.py `
        .claude/scripts/data_modules/tests/test_rag_adapter.py `
        --basetemp $baseTemp `
        --no-cov `
        -p no:cacheprovider
    exit $LASTEXITCODE
}

python -m pytest -q `
    .claude/scripts/data_modules/tests `
    --basetemp $baseTemp `
    -p no:cacheprovider
exit $LASTEXITCODE
