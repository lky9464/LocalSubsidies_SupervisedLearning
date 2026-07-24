# Build update-vX.Y.Z.zip for offline incremental update (Release asset or USB).
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\build_offline_update_package.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\build_offline_update_package.ps1 -Version 0.5.1
param(
    [string]$Version = "",
    [string]$OutDir = "dist"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

function Normalize-Rel([string]$Path) {
    return ($Path -replace '\\', '/').Trim('/')
}

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
$updateType = $manifest.update_types.$typeName
if (-not $updateType) {
    throw "unknown update_type: $typeName"
}

$paths = @()
$paths += @($updateType.copy_paths | ForEach-Object { [string]$_ })
$paths += @($release.extra_copy_paths | ForEach-Object { [string]$_ })
$rootFiles = @()
$rootFiles += @($updateType.copy_root_files | ForEach-Object { [string]$_ })
$rootFiles += @($release.extra_root_files | ForEach-Object { [string]$_ })
$rootFiles += @("offline_update_manifest.json")
$configExamples = @($updateType.copy_config_examples | ForEach-Object { [string]$_ })

$stage = Join-Path $env:TEMP ("lsl_update_build_" + [guid]::NewGuid().ToString("n"))
New-Item -ItemType Directory -Path $stage -Force | Out-Null

try {
    foreach ($rel in (($paths + $rootFiles + $configExamples) | Select-Object -Unique)) {
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

    if ($updateType.web_out_zip) {
        $zipRoot = Join-Path $Root "web-out.zip"
        if (Test-Path -LiteralPath $zipRoot) {
            Copy-Item -LiteralPath $zipRoot -Destination (Join-Path $stage "web-out.zip") -Force
        } elseif (Test-Path -LiteralPath (Join-Path $Root "web\out\index.html")) {
            Compress-Archive -Path (Join-Path $Root "web\out\*") -DestinationPath (Join-Path $stage "web-out.zip") -Force
        } else {
            throw "web-out.zip or web/out/index.html required for update package"
        }
    }

    New-Item -ItemType Directory -Path (Join-Path $Root $OutDir) -Force | Out-Null
    $outZip = Join-Path (Join-Path $Root $OutDir) ("update-v{0}.zip" -f $targetVersion)
    if (Test-Path -LiteralPath $outZip) { Remove-Item -LiteralPath $outZip -Force }
    Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $outZip -Force
    Write-Host "Created $outZip"
}
finally {
    Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
}
