# Build update-to-vX.Y.Z.zip for offline full-sync update (Release / USB).
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\build_offline_update_package.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\build_offline_update_package.ps1 -Version 0.5.2
param(
    [string]$Version = "",
    [string]$OutDir = "dist"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$manifestPath = Join-Path $Root "offline_update_manifest.json"
if (-not (Test-Path -LiteralPath $manifestPath)) {
    throw "offline_update_manifest.json not found"
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json

$targetVersion = if ($Version) { $Version } else { [string]$manifest.target_version }
$release = @($manifest.releases | Where-Object { [string]$_.version -eq $targetVersion })[0]
if (-not $release) {
    throw "No release entry for version $targetVersion in offline_update_manifest.json"
}

$typeName = [string]$release.update_type
if (-not $typeName) { $typeName = "full_sync" }
$updateType = $manifest.update_types.$typeName
if (-not $updateType) {
    throw "unknown update_type: $typeName"
}

$paths = @()
if ($updateType.PSObject.Properties.Name -contains "copy_paths" -and $updateType.copy_paths) {
    $paths += @($updateType.copy_paths | ForEach-Object { [string]$_ })
}
if ($release.PSObject.Properties.Name -contains "extra_copy_paths" -and $release.extra_copy_paths) {
    $paths += @($release.extra_copy_paths | ForEach-Object { [string]$_ })
}
$rootFiles = @()
if ($updateType.PSObject.Properties.Name -contains "copy_root_files" -and $updateType.copy_root_files) {
    $rootFiles += @($updateType.copy_root_files | ForEach-Object { [string]$_ })
}
if ($release.PSObject.Properties.Name -contains "extra_root_files" -and $release.extra_root_files) {
    $rootFiles += @($release.extra_root_files | ForEach-Object { [string]$_ })
}
$rootFiles += @("offline_update_manifest.json", "UpdateOffline.bat")
$rootFiles += @(
    "scripts/apply_offline_update.ps1",
    "scripts/build_offline_update_package.ps1",
    "scripts/cleanup_legacy_artifacts.py"
)

$stage = Join-Path $env:TEMP ("lsl_update_build_" + [guid]::NewGuid().ToString("n"))
New-Item -ItemType Directory -Path $stage -Force | Out-Null

try {
    foreach ($rel in (($paths + $rootFiles) | Select-Object -Unique)) {
        if ($rel -eq "web/out") {
            # packed as web-out.zip below
            continue
        }
        if ($rel -eq "configs") {
            # only examples / default — never local.yaml
            foreach ($cf in @(
                    "configs/default.yaml",
                    "configs/local.yaml.example",
                    "configs/tune.yaml",
                    "configs/tune_local.yaml.example",
                    "configs/tune_run.yaml.example"
                )) {
                $src = Join-Path $Root ($cf -replace '/', '\')
                if (-not (Test-Path -LiteralPath $src)) { continue }
                $dst = Join-Path $stage ($cf -replace '/', '\')
                $parent = Split-Path -Parent $dst
                New-Item -ItemType Directory -Path $parent -Force | Out-Null
                Copy-Item -LiteralPath $src -Destination $dst -Force
            }
            continue
        }
        $relWin = ($rel -replace '/', '\')
        $src = Join-Path $Root $relWin
        if (-not (Test-Path -LiteralPath $src)) {
            Write-Warning "skip missing: $rel"
            continue
        }
        $dst = Join-Path $stage $relWin
        $parent = Split-Path -Parent $dst
        if ($parent) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
        if (Test-Path -LiteralPath $src -PathType Container) {
            Copy-Item -LiteralPath $src -Destination $dst -Recurse -Force
        } else {
            Copy-Item -LiteralPath $src -Destination $dst -Force
        }
    }

    # Always ship web-out.zip for reliable UI replace
    $stageWebZip = Join-Path $stage "web-out.zip"
    $zipRoot = Join-Path $Root "web-out.zip"
    if (Test-Path -LiteralPath $zipRoot) {
        Copy-Item -LiteralPath $zipRoot -Destination $stageWebZip -Force
    } elseif (Test-Path -LiteralPath (Join-Path $Root "web\out\index.html")) {
        Compress-Archive -Path (Join-Path $Root "web\out\*") -DestinationPath $stageWebZip -Force
    } else {
        throw "web-out.zip or web/out/index.html required for update package"
    }

    New-Item -ItemType Directory -Path (Join-Path $Root $OutDir) -Force | Out-Null
    $outZip = Join-Path (Join-Path $Root $OutDir) ("update-to-v{0}.zip" -f $targetVersion)
    if (Test-Path -LiteralPath $outZip) { Remove-Item -LiteralPath $outZip -Force }
    Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $outZip -Force
    Write-Host "Created $outZip"
    Write-Host "Also publish wheels-win-amd64-py312.zip on the Release when wheels_baseline/reinstall is true."
}
finally {
    Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
}
