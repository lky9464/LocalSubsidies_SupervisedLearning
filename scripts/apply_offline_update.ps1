# Apply incremental offline update (method 1: changed paths only).
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\apply_offline_update.ps1 -ProjectRoot . -Source D:\USB\update-v0.5.1
#   powershell -ExecutionPolicy Bypass -File scripts\apply_offline_update.ps1 -ProjectRoot . -Source D:\USB\update-v0.5.1.zip
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot,
    [Parameter(Mandatory = $true)]
    [string]$Source,
    [switch]$Force,
    [switch]$WhatIf
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step([string]$Message) {
    Write-Host "[update] $Message"
}

function Normalize-Rel([string]$Path) {
    return ($Path -replace '\\', '/').Trim('/')
}

function Parse-Version([string]$Text) {
    $v = ($Text -replace '^v', '').Trim()
    if (-not $v) { return $null }
    return [version]$v
}

function Read-CurrentVersion([string]$HistoryPath) {
    if (-not (Test-Path -LiteralPath $HistoryPath)) { return $null }
    foreach ($line in Get-Content -LiteralPath $HistoryPath -Encoding UTF8) {
        if ($line -match '[*][*]v?(\d+\.\d+\.\d+)[*][*]') {
            return $matches[1]
        }
    }
    return $null
}

function Test-Preserved([string]$RelPath, [string[]]$PreserveList) {
    $rel = Normalize-Rel $RelPath
    foreach ($item in $PreserveList) {
        $p = Normalize-Rel $item
        if ($rel -eq $p) { return $true }
        if ($rel.StartsWith("$p/")) { return $true }
    }
    return $false
}

function Copy-RelTree {
    param(
        [string]$SourceRoot,
        [string]$DestRoot,
        [string]$RelPath,
        [string[]]$PreserveList,
        [switch]$WhatIf
    )
    $rel = Normalize-Rel $RelPath
    if (Test-Preserved $rel $PreserveList) {
        Write-Step "skip (preserve): $rel"
        return
    }
    $src = Join-Path $SourceRoot ($rel -replace '/', '\')
    if (-not (Test-Path -LiteralPath $src)) {
        Write-Warning "missing in update package: $rel"
        return
    }
    $dst = Join-Path $DestRoot ($rel -replace '/', '\')
    Write-Step "copy: $rel"
    if ($WhatIf) { return }
    $parent = Split-Path -Parent $dst
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    if (Test-Path -LiteralPath $src -PathType Container) {
        Copy-Item -LiteralPath $src -Destination $dst -Recurse -Force
    } else {
        Copy-Item -LiteralPath $src -Destination $dst -Force
    }
}

function Expand-WebOutZip {
    param(
        [string]$ZipPath,
        [string]$ProjectRoot,
        [switch]$WhatIf
    )
    if (-not (Test-Path -LiteralPath $ZipPath)) {
        Write-Warning "web-out.zip not found: $ZipPath"
        return
    }
    Write-Step "extract UI: web-out.zip -> web/out"
    if ($WhatIf) { return }
    $temp = Join-Path $env:TEMP ("lsl_webout_" + [guid]::NewGuid().ToString("n"))
    New-Item -ItemType Directory -Path $temp -Force | Out-Null
    try {
        Expand-Archive -LiteralPath $ZipPath -DestinationPath $temp -Force
        $dest = Join-Path $ProjectRoot "web\out"
        New-Item -ItemType Directory -Path $dest -Force | Out-Null
        Get-ChildItem -LiteralPath $dest -Force | Remove-Item -Recurse -Force
        Copy-Item -LiteralPath (Join-Path $temp '*') -Destination $dest -Recurse -Force
    } finally {
        Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$tempSource = $null
$sourceRoot = $Source

if ($Source -match '\.zip$') {
    $tempSource = Join-Path $env:TEMP ("lsl_update_" + [guid]::NewGuid().ToString("n"))
    New-Item -ItemType Directory -Path $tempSource -Force | Out-Null
    Expand-Archive -LiteralPath $Source -DestinationPath $tempSource -Force
    $sourceRoot = $tempSource
} else {
    $sourceRoot = (Resolve-Path -LiteralPath $Source).Path
}

try {
    $manifestPath = Join-Path $sourceRoot "offline_update_manifest.json"
    if (-not (Test-Path -LiteralPath $manifestPath)) {
        throw "offline_update_manifest.json not found in update package: $sourceRoot"
    }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json

    $targetVersion = [string]$manifest.target_version
    $release = @($manifest.releases | Where-Object { [string]$_.version -eq $targetVersion })[0]
    if (-not $release) {
        throw "manifest has no release entry for version $targetVersion"
    }

    $currentVersion = Read-CurrentVersion (Join-Path $ProjectRoot "docs\VERSION_HISTORY.md")
    $fromList = @($release.from_versions | ForEach-Object { [string]$_ })
    if ($currentVersion -and $fromList.Count -gt 0 -and ($fromList -notcontains $currentVersion)) {
        $msg = "installed=$currentVersion expected one of: $($fromList -join ', ')"
        if (-not $Force) {
            throw "Version mismatch ($msg). Re-run with -Force if intentional."
        }
        Write-Warning "Version mismatch ($msg) — continuing due to -Force"
    }

    $typeName = [string]$release.update_type
    $updateType = $manifest.update_types.$typeName
    if (-not $updateType) {
        throw "unknown update_type: $typeName"
    }

    $preserve = @($manifest.preserve_always | ForEach-Object { [string]$_ })
    $paths = @()
    $paths += @($updateType.copy_paths | ForEach-Object { [string]$_ })
    $paths += @($release.extra_copy_paths | ForEach-Object { [string]$_ })
    $rootFiles = @()
    $rootFiles += @($updateType.copy_root_files | ForEach-Object { [string]$_ })
    $rootFiles += @($release.extra_root_files | ForEach-Object { [string]$_ })
    $configExamples = @($updateType.copy_config_examples | ForEach-Object { [string]$_ })

    Write-Step "target v$targetVersion ($($updateType.label))"
    if ($currentVersion) { Write-Step "installed v$currentVersion" }
    if ($release.notes) { Write-Step $release.notes }

    foreach ($rel in ($paths | Select-Object -Unique)) {
        Copy-RelTree -SourceRoot $sourceRoot -DestRoot $ProjectRoot -RelPath $rel -PreserveList $preserve -WhatIf:$WhatIf
    }

    foreach ($rel in ($rootFiles | Select-Object -Unique)) {
        Copy-RelTree -SourceRoot $sourceRoot -DestRoot $ProjectRoot -RelPath $rel -PreserveList $preserve -WhatIf:$WhatIf
    }

    foreach ($rel in ($configExamples | Select-Object -Unique)) {
        Copy-RelTree -SourceRoot $sourceRoot -DestRoot $ProjectRoot -RelPath $rel -PreserveList $preserve -WhatIf:$WhatIf
    }

    if ($updateType.web_out_zip) {
        $zip = Join-Path $sourceRoot "web-out.zip"
        Expand-WebOutZip -ZipPath $zip -ProjectRoot $ProjectRoot -WhatIf:$WhatIf
    }

    $wheelsReinstall = [bool]$release.wheels_reinstall -or [bool]$updateType.wheels_reinstall
    $reqSrc = Join-Path $sourceRoot "requirements.txt"
    $reqDst = Join-Path $ProjectRoot "requirements.txt"
    if ((Test-Path -LiteralPath $reqSrc) -and (Test-Path -LiteralPath $reqDst)) {
        $hashSrc = (Get-FileHash -LiteralPath $reqSrc -Algorithm SHA256).Hash
        $hashDst = (Get-FileHash -LiteralPath $reqDst -Algorithm SHA256).Hash
        if ($hashSrc -ne $hashDst) {
            $wheelsReinstall = $true
            Write-Warning "requirements.txt changed — run SetupOffline.bat after update."
        }
    }

    Write-Host ""
    Write-Host "Update applied (target v$targetVersion)." -ForegroundColor Green
    if ($wheelsReinstall) {
        Write-Host "Next: SetupOffline.bat (wheels / .venv refresh required)" -ForegroundColor Yellow
    } else {
        Write-Host "Next: RunWebNext.bat restart" -ForegroundColor Yellow
    }
    Write-Host "configs\local.yaml and data_root were not modified."
}
finally {
    if ($tempSource -and (Test-Path -LiteralPath $tempSource)) {
        Remove-Item -LiteralPath $tempSource -Recurse -Force -ErrorAction SilentlyContinue
    }
}
