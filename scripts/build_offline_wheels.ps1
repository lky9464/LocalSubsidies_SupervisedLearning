# 온라인 PC에서만 실행: PyPI에서 Windows x64 + Python 3.12용 wheel을 받아
# vendor/wheels 에 저장하고, Release 업로드용 zip을 dist/ 에 만듭니다.
#
#   powershell -ExecutionPolicy Bypass -File .\scripts\build_offline_wheels.ps1
#
# 이후 (선택):
#   gh release upload v0.3.0 .\dist\wheels-win-amd64-py312.zip --clobber

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$pyVer = "3.12"
$wheelDir = Join-Path $Root "vendor\wheels"
$distDir = Join-Path $Root "dist"
$lockFile = Join-Path $Root "requirements.lock.txt"
$zipName = "wheels-win-amd64-py312.zip"
$zipPath = Join-Path $distDir $zipName

if (-not (Test-Path $lockFile)) {
    Write-Host "ERROR: requirements.lock.txt 없음"
    exit 1
}

New-Item -ItemType Directory -Force -Path $wheelDir | Out-Null
New-Item -ItemType Directory -Force -Path $distDir | Out-Null

# 기존 wheel 비우기 (재현 가능한 묶음)
Get-ChildItem -Path $wheelDir -File -ErrorAction SilentlyContinue | Remove-Item -Force

Write-Host "Downloading wheels into $wheelDir ..."
Write-Host "  Target: Windows amd64, Python $pyVer (binary only)"
Write-Host ""

$pip = $null
$venvPip = Join-Path $Root ".venv\Scripts\pip.exe"
if (Test-Path $venvPip) {
    $pip = $venvPip
} else {
    $pip = "pip"
}

& $pip download `
    -r $lockFile `
    -d $wheelDir `
    --platform win_amd64 `
    --python-version $pyVer `
    --implementation cp `
    --abi cp312 `
    --only-binary=:all:

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "WARN: platform-specific download failed. Retrying without platform pins"
    Write-Host "      (use the same Python 3.12 x64 as the offline target PC)."
    & $pip download -r $lockFile -d $wheelDir --only-binary=:all:
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: pip download failed."
        exit 1
    }
}

$count = (Get-ChildItem -Path $wheelDir -File).Count
Write-Host ""
Write-Host "Downloaded $count files."

if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}

Write-Host "Creating $zipPath ..."
Compress-Archive -Path (Join-Path $wheelDir "*") -DestinationPath $zipPath -Force

$sizeMb = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)
Write-Host ""
Write-Host "Done."
Write-Host "  Wheels folder : $wheelDir"
Write-Host "  Zip for Release: $zipPath ($sizeMb MB)"
Write-Host ""
Write-Host "Upload example:"
Write-Host "  gh release upload v0.3.0 `"$zipPath`" --clobber"
Write-Host "Docs: docs\offline_setup.md"
