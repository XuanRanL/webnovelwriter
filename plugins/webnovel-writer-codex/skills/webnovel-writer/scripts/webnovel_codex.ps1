Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = ""
$PluginRoot = $env:WEBNOVEL_PLUGIN_ROOT

$i = 0
while ($i -lt $args.Count) {
    $arg = [string]$args[$i]
    if (($arg -eq "-ProjectRoot") -or ($arg -eq "--project-root")) {
        if ($i + 1 -ge $args.Count) {
            throw "$arg requires a value"
        }
        $ProjectRoot = [string]$args[$i + 1]
        $i += 2
        continue
    }
    if (($arg -eq "-PluginRoot") -or ($arg -eq "--plugin-root")) {
        if ($i + 1 -ge $args.Count) {
            throw "$arg requires a value"
        }
        $PluginRoot = [string]$args[$i + 1]
        $i += 2
        continue
    }
    break
}

$CommandArgs = @()
if ($i -lt $args.Count) {
    $CommandArgs = @($args[$i..($args.Count - 1)])
}

function Resolve-ExistingPath {
    param([string]$PathValue)
    if ([string]::IsNullOrWhiteSpace($PathValue)) {
        return $null
    }
    if (Test-Path -LiteralPath $PathValue) {
        return (Resolve-Path -LiteralPath $PathValue).Path
    }
    return $null
}

function Find-WebnovelPluginRoot {
    param([string]$StartPath)

    $explicit = Resolve-ExistingPath $PluginRoot
    if ($explicit) {
        $script = Join-Path $explicit "scripts\webnovel.py"
        if (Test-Path -LiteralPath $script) {
            return $explicit
        }
    }

    $cursor = Resolve-ExistingPath $StartPath
    if (-not $cursor) {
        $cursor = (Get-Location).Path
    }

    while ($true) {
        $nested = Join-Path $cursor "webnovel-writer\scripts\webnovel.py"
        if (Test-Path -LiteralPath $nested) {
            return (Join-Path $cursor "webnovel-writer")
        }

        $direct = Join-Path $cursor "scripts\webnovel.py"
        $directSkill = Join-Path $cursor "skills\webnovel-write\SKILL.md"
        if ((Test-Path -LiteralPath $direct) -and (Test-Path -LiteralPath $directSkill)) {
            return $cursor
        }

        $parent = Split-Path -Parent $cursor
        if ([string]::IsNullOrWhiteSpace($parent) -or $parent -eq $cursor) {
            break
        }
        $cursor = $parent
    }

    throw "Cannot locate webnovel plugin root. Run from the repo/workspace or set WEBNOVEL_PLUGIN_ROOT."
}

if (-not $CommandArgs -or $CommandArgs.Count -eq 0) {
    $CommandArgs = @("--help")
}

$project = Resolve-ExistingPath $ProjectRoot
if (-not $project) {
    $project = (Get-Location).Path
}

$resolvedPluginRoot = Find-WebnovelPluginRoot -StartPath $project
$entry = Join-Path $resolvedPluginRoot "scripts\webnovel.py"

& python -X utf8 $entry --project-root $project @CommandArgs
exit $LASTEXITCODE
