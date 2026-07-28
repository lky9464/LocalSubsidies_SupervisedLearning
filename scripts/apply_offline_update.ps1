# Apply offline update (full sync to latest, or legacy hop).
# ASCII messages only (codepage-safe).
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\apply_offline_update.ps1 -ProjectRoot .
#   powershell -ExecutionPolicy Bypass -File scripts\apply_offline_update.ps1 -ProjectRoot . -Source D:\USB\update-to-v0.5.2.zip
#   powershell ... -AutoWheels   # unpack wheels zip + run SetupOffline when needed
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot,
    [string]$Source = "",
    [switch]$Force,
    [switch]$WhatIf,
    [switch]$AutoWheels
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step([string]$Message) {
    Write-Host "[update] $Message"
}

function Normalize-Rel([string]$Path) {
    return ($Path -replace '\\', '/').Trim('/')
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

function Test-VersionAtLeast([string]$Installed, [string]$Min) {
    if (-not $Installed -or -not $Min) { return $true }
    try {
        return ([version]($Installed -replace '^v', '')) -ge ([version]($Min -replace '^v', ''))
    } catch {
        return $true
    }
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

function Find-UpdateZip([string]$ProjectRoot, [string]$HintDir) {
    $dirs = @()
    if ($HintDir) { $dirs += $HintDir }
    $dirs += $ProjectRoot
    $dirs += (Join-Path $ProjectRoot "update")
    $dirs += (Join-Path $ProjectRoot "patch")
    $cands = @()
    foreach ($d in ($dirs | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $d -PathType Container)) { continue }
        $cands += Get-ChildItem -LiteralPath $d -File -ErrorAction SilentlyContinue |
            Where-Object {
                $_.Name -match '^update-to-v\d+\.\d+\.\d+\.zip$' -or
                $_.Name -match '^update-v\d+\.\d+\.\d+\.zip$' -or
                $_.Name -match '^patch-to-v\d+\.\d+\.\d+\.zip$'
            }
    }
    if (-not $cands -or $cands.Count -eq 0) { return $null }
    $best = $null
    $bestVer = $null
    foreach ($f in $cands) {
        if ($f.Name -match 'v(\d+\.\d+\.\d+)') {
            $v = [version]$matches[1]
            if ($null -eq $bestVer -or $v -gt $bestVer) {
                $bestVer = $v
                $best = $f.FullName
            }
        }
    }
    return $best
}

function Find-WheelsZip([string]$ProjectRoot, [string]$BesideSource) {
    $dirs = @()
    if ($BesideSource) {
        $p = Split-Path -Parent $BesideSource
        if ($p) { $dirs += $p }
    }
    $dirs += $ProjectRoot
    $dirs += (Join-Path $ProjectRoot "vendor")
    foreach ($d in ($dirs | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $d -PathType Container)) { continue }
        $hit = Get-ChildItem -LiteralPath $d -File -Filter "wheels-win-amd64-py312.zip" -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($hit) { return $hit.FullName }
    }
    return $null
}

function Copy-RelTree {
    param(
        [string]$SourceRoot,
        [string]$DestRoot,
        [string]$RelPath,
        [string[]]$PreserveList,
        [string[]]$SkipFiles,
        [switch]$WhatIf
    )
    $rel = Normalize-Rel $RelPath
    if (Test-Preserved $rel $PreserveList) {
        Write-Step "skip (preserve): $rel"
        return
    }
    foreach ($skip in $SkipFiles) {
        if ((Normalize-Rel $skip) -eq $rel) {
            Write-Step "skip (local): $rel"
            return
        }
    }
    $src = Join-Path $SourceRoot ($rel -replace '/', '\')
    if (-not (Test-Path -LiteralPath $src)) {
        Write-Warning "missing in update package: $rel"
        return
    }
    $dst = Join-Path $DestRoot ($rel -replace '/', '\')
    Write-Step "copy: $rel"
    if ($WhatIf) { return }

    if (Test-Path -LiteralPath $src -PathType Container) {
        # Directory copy: merge, but never overwrite preserved files inside
        Get-ChildItem -LiteralPath $src -Recurse -File | ForEach-Object {
            $sub = $_.FullName.Substring($src.Length).TrimStart('\', '/')
            $subNorm = Normalize-Rel (($rel + '/' + ($sub -replace '\\', '/')).Trim('/'))
            if (Test-Preserved $subNorm $PreserveList) { return }
            foreach ($skip in $SkipFiles) {
                if ((Normalize-Rel $skip) -eq $subNorm) { return }
            }
            $destFile = Join-Path $dst $sub
            $parent = Split-Path -Parent $destFile
            if (-not (Test-Path -LiteralPath $parent)) {
                New-Item -ItemType Directory -Path $parent -Force | Out-Null
            }
            Copy-Item -LiteralPath $_.FullName -Destination $destFile -Force
        }
    } else {
        $parent = Split-Path -Parent $dst
        if ($parent -and -not (Test-Path -LiteralPath $parent)) {
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
        }
        Copy-Item -LiteralPath $src -Destination $dst -Force
    }
}

function Expand-WebOutZip {
    param(
        [string]$ZipPath,
        [string]$ProjectRoot,
        [switch]$WhatIf
    )
    if (-not (Test-Path -LiteralPath $ZipPath)) { return }
    Write-Step "extract UI: web-out.zip -> web/out"
    if ($WhatIf) { return }
    $temp = Join-Path $env:TEMP ("lsl_webout_" + [guid]::NewGuid().ToString("n"))
    New-Item -ItemType Directory -Path $temp -Force | Out-Null
    try {
        Expand-Archive -LiteralPath $ZipPath -DestinationPath $temp -Force
        $dest = Join-Path $ProjectRoot "web\out"
        New-Item -ItemType Directory -Path $dest -Force | Out-Null
        Get-ChildItem -LiteralPath $dest -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
        Copy-Item -LiteralPath (Join-Path $temp '*') -Destination $dest -Recurse -Force
    } finally {
        Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Install-WheelsZip {
    param(
        [string]$WheelsZip,
        [string]$ProjectRoot,
        [switch]$WhatIf
    )
    $vendor = Join-Path $ProjectRoot "vendor\wheels"
    Write-Step "extract wheels -> vendor/wheels"
    if ($WhatIf) { return }
    New-Item -ItemType Directory -Path $vendor -Force | Out-Null
    $temp = Join-Path $env:TEMP ("lsl_wheels_" + [guid]::NewGuid().ToString("n"))
    New-Item -ItemType Directory -Path $temp -Force | Out-Null
    try {
        Expand-Archive -LiteralPath $WheelsZip -DestinationPath $temp -Force
        $whl = Get-ChildItem -LiteralPath $temp -Recurse -Filter "*.whl" -ErrorAction SilentlyContinue
        if (-not $whl -or $whl.Count -eq 0) {
            throw "No .whl files inside wheels zip"
        }
        Get-ChildItem -LiteralPath $vendor -Filter "*.whl" -ErrorAction SilentlyContinue | Remove-Item -Force
        foreach ($f in $whl) {
            Copy-Item -LiteralPath $f.FullName -Destination (Join-Path $vendor $f.Name) -Force
        }
    } finally {
        Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Get-JsonProp($Obj, [string]$Name, $Default = $null) {
    if ($null -eq $Obj) { return $Default }
    if ($Obj.PSObject.Properties.Name -contains $Name) {
        return $Obj.$Name
    }
    return $Default
}

# --- resolve Source ---
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$sourceHint = ""
if (-not $Source) {
    $Source = Find-UpdateZip -ProjectRoot $ProjectRoot -HintDir ""
    if (-not $Source) {
        throw "No update zip found. Put update-to-vX.Y.Z.zip next to UpdateOffline.bat / project root."
    }
    Write-Step "auto-selected: $Source"
} elseif (-not (Test-Path -LiteralPath $Source)) {
    throw "Not found: $Source"
} else {
    $Source = (Resolve-Path -LiteralPath $Source).Path
}
$sourceHint = $Source

$tempSource = $null
$sourceRoot = $Source
if ($Source -match '\.zip$') {
    $tempSource = Join-Path $env:TEMP ("lsl_update_" + [guid]::NewGuid().ToString("n"))
    New-Item -ItemType Directory -Path $tempSource -Force | Out-Null
    Expand-Archive -LiteralPath $Source -DestinationPath $tempSource -Force
    # zip may contain a single top folder
    $manifestProbe = Join-Path $tempSource "offline_update_manifest.json"
    if (-not (Test-Path -LiteralPath $manifestProbe)) {
        $inner = Get-ChildItem -LiteralPath $tempSource -Directory | Select-Object -First 1
        if ($inner) { $sourceRoot = $inner.FullName } else { $sourceRoot = $tempSource }
    } else {
        $sourceRoot = $tempSource
    }
} else {
    $sourceRoot = (Resolve-Path -LiteralPath $Source).Path
}

try {
    $manifestPath = Join-Path $sourceRoot "offline_update_manifest.json"
    if (-not (Test-Path -LiteralPath $manifestPath)) {
        throw "offline_update_manifest.json not found in update package"
    }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json

    $targetVersion = [string]$manifest.target_version
    $release = @($manifest.releases | Where-Object { [string]$_.version -eq $targetVersion })[0]
    if (-not $release) {
        throw "manifest has no release entry for version $targetVersion"
    }

    $currentVersion = Read-CurrentVersion (Join-Path $ProjectRoot "docs\VERSION_HISTORY.md")
    $fromMin = [string](Get-JsonProp $release "from_min" "")
    if (-not $fromMin) { $fromMin = [string](Get-JsonProp $manifest "from_min" "") }
    $fromList = @()
    $fromVersions = Get-JsonProp $release "from_versions" $null
    if ($fromVersions) {
        $fromList = @($fromVersions | ForEach-Object { [string]$_ })
    }

    $mode = [string](Get-JsonProp $manifest "mode" "hop")
    if (-not $mode) { $mode = "hop" }

    if ($currentVersion) {
        Write-Step "installed v$currentVersion"
        if ($mode -eq "full_sync" -or $fromMin) {
            if (-not (Test-VersionAtLeast $currentVersion $fromMin)) {
                $msg = "installed=v$currentVersion below from_min=v$fromMin"
                if (-not $Force) { throw "Version too old ($msg). Use Force or reinstall from Source zip." }
                Write-Warning $msg
            }
        } elseif ($fromList.Count -gt 0 -and ($fromList -notcontains $currentVersion)) {
            $msg = "installed=$currentVersion expected one of: $($fromList -join ', ')"
            if (-not $Force) { throw "Version mismatch ($msg). Re-run with -Force if intentional." }
            Write-Warning $msg
        }
    } else {
        Write-Step "installed version unknown (ok for full_sync)"
    }

    $typeName = [string](Get-JsonProp $release "update_type" "full_sync")
    if (-not $typeName) { $typeName = "full_sync" }
    $updateType = $manifest.update_types.$typeName
    if (-not $updateType) {
        throw "unknown update_type: $typeName"
    }

    $preserve = @()
    $preserveAlways = Get-JsonProp $manifest "preserve_always" $null
    if ($preserveAlways) {
        $preserve = @($preserveAlways | ForEach-Object { [string]$_ })
    }
    $skipFiles = @()
    $skipRel = Get-JsonProp $updateType "skip_relative_files" $null
    if ($skipRel) {
        $skipFiles += @($skipRel | ForEach-Object { [string]$_ })
    }

    $paths = @()
    $copyPaths = Get-JsonProp $updateType "copy_paths" $null
    if ($copyPaths) {
        $paths += @($copyPaths | ForEach-Object { [string]$_ })
    }
    $extraCopy = Get-JsonProp $release "extra_copy_paths" $null
    if ($extraCopy) {
        $paths += @($extraCopy | ForEach-Object { [string]$_ })
    }
    $rootFiles = @()
    $copyRoot = Get-JsonProp $updateType "copy_root_files" $null
    if ($copyRoot) {
        $rootFiles += @($copyRoot | ForEach-Object { [string]$_ })
    }
    $extraRoot = Get-JsonProp $release "extra_root_files" $null
    if ($extraRoot) {
        $rootFiles += @($extraRoot | ForEach-Object { [string]$_ })
    }

    Write-Step "target v$targetVersion ($($updateType.label))"
    $notes = Get-JsonProp $release "notes" $null
    if ($notes) { Write-Step ([string]$notes) }

    # Hash installed requirements BEFORE overwrite (for wheels decision)
    $reqBeforeHash = $null
    $reqDstPath = Join-Path $ProjectRoot "requirements.txt"
    if (Test-Path -LiteralPath $reqDstPath) {
        $reqBeforeHash = (Get-FileHash -LiteralPath $reqDstPath -Algorithm SHA256).Hash
    }
    $reqSrcPath = Join-Path $sourceRoot "requirements.txt"
    $reqPkgHash = $null
    if (Test-Path -LiteralPath $reqSrcPath) {
        $reqPkgHash = (Get-FileHash -LiteralPath $reqSrcPath -Algorithm SHA256).Hash
    }

    foreach ($rel in ($paths | Select-Object -Unique)) {
        if ($rel -eq "web/out" -and (Test-Path -LiteralPath (Join-Path $sourceRoot "web-out.zip"))) {
            # prefer zip extract below
            continue
        }
        Copy-RelTree -SourceRoot $sourceRoot -DestRoot $ProjectRoot -RelPath $rel `
            -PreserveList $preserve -SkipFiles $skipFiles -WhatIf:$WhatIf
    }

    foreach ($rel in ($rootFiles | Select-Object -Unique)) {
        Copy-RelTree -SourceRoot $sourceRoot -DestRoot $ProjectRoot -RelPath $rel `
            -PreserveList $preserve -SkipFiles $skipFiles -WhatIf:$WhatIf
    }

    # Always refresh apply scripts if present in package
    foreach ($extra in @(
            "scripts/apply_offline_update.ps1",
            "scripts/build_offline_update_package.ps1",
            "scripts/cleanup_legacy_artifacts.py"
        )) {
        $p = Join-Path $sourceRoot ($extra -replace '/', '\')
        if (Test-Path -LiteralPath $p) {
            Copy-RelTree -SourceRoot $sourceRoot -DestRoot $ProjectRoot -RelPath $extra `
                -PreserveList $preserve -SkipFiles $skipFiles -WhatIf:$WhatIf
        }
    }

    $webOutCopied = Test-Path -LiteralPath (Join-Path $ProjectRoot "web\out\index.html")
    $wantWebZip = [bool](Get-JsonProp $updateType "web_out_zip" $false)
    if ($wantWebZip -or (Test-Path -LiteralPath (Join-Path $sourceRoot "web-out.zip"))) {
        $zip = Join-Path $sourceRoot "web-out.zip"
        if (Test-Path -LiteralPath $zip) {
            Expand-WebOutZip -ZipPath $zip -ProjectRoot $ProjectRoot -WhatIf:$WhatIf
            $webOutCopied = $true
        }
    }
    if (-not $webOutCopied -and (Test-Path -LiteralPath (Join-Path $sourceRoot "web\out\index.html"))) {
        Copy-RelTree -SourceRoot $sourceRoot -DestRoot $ProjectRoot -RelPath "web/out" `
            -PreserveList $preserve -SkipFiles $skipFiles -WhatIf:$WhatIf
    }

    $wheelsReinstall = [bool](Get-JsonProp $release "wheels_reinstall" $false) `
        -or [bool](Get-JsonProp $updateType "wheels_reinstall" $false) `
        -or [bool](Get-JsonProp $release "wheels_baseline" $false)
    if (-not $wheelsReinstall -and $reqBeforeHash -and $reqPkgHash -and ($reqBeforeHash -ne $reqPkgHash)) {
        $wheelsReinstall = $true
        Write-Step "requirements.txt changed -> wheels refresh needed"
    }

    $wheelsZip = Find-WheelsZip -ProjectRoot $ProjectRoot -BesideSource $sourceHint
    $didWheels = $false
    if ($wheelsReinstall) {
        if ($wheelsZip) {
            Write-Step "wheels zip found: $wheelsZip"
            Install-WheelsZip -WheelsZip $wheelsZip -ProjectRoot $ProjectRoot -WhatIf:$WhatIf
            $didWheels = $true
            if ($AutoWheels -and -not $WhatIf) {
                $setup = Join-Path $ProjectRoot "SetupOffline.bat"
                if (Test-Path -LiteralPath $setup) {
                    Write-Step "running SetupOffline.bat _run ..."
                    $p = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "`"$setup`" _run" -WorkingDirectory $ProjectRoot -Wait -PassThru
                    if ($p.ExitCode -ne 0) {
                        Write-Warning "SetupOffline exit code $($p.ExitCode)"
                    }
                }
            }
        } else {
            Write-Warning "wheels-win-amd64-py312.zip not found next to update zip / project root."
            Write-Warning "Copy it from the GitHub Release, then run SetupOffline.bat"
        }
    }

    Write-Host ""
    Write-Host "Update applied (target v$targetVersion)." -ForegroundColor Green
    Write-Host "Preserved: configs\local.yaml, .venv, vendor\wheels, data_root"
    if ($wheelsReinstall -and -not $didWheels) {
        Write-Host "Next: copy wheels-win-amd64-py312.zip, then SetupOffline.bat" -ForegroundColor Yellow
    } elseif ($wheelsReinstall -and $didWheels -and -not $AutoWheels) {
        Write-Host "Next: SetupOffline.bat   then   RunWebNext.bat restart" -ForegroundColor Yellow
    } else {
        Write-Host "Next: RunWebNext.bat restart" -ForegroundColor Yellow
    }
    Write-Host "Optional: if UI shows mixed old results, run CleanupLegacy.bat (keeps raw)."
}
finally {
    if ($tempSource -and (Test-Path -LiteralPath $tempSource)) {
        Remove-Item -LiteralPath $tempSource -Recurse -Force -ErrorAction SilentlyContinue
    }
}
