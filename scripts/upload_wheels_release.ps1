# Release에 wheels zip 업로드 (사전: gh auth login)
#   powershell -ExecutionPolicy Bypass -File .\scripts\upload_wheels_release.ps1
#   powershell -ExecutionPolicy Bypass -File .\scripts\upload_wheels_release.ps1 -Tag v0.3.0

param(
    [string]$Tag = "v0.3.0"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$zip = Join-Path $Root "dist\wheels-win-amd64-py312.zip"

$gh = "${env:ProgramFiles}\GitHub CLI\gh.exe"
if (-not (Test-Path $gh)) {
    $gh = "${env:LocalAppData}\Programs\GitHub CLI\gh.exe"
}
if (-not (Test-Path $gh)) {
    $gh = "gh"
}

if (-not (Test-Path $zip)) {
    Write-Host "ERROR: $zip 없음. 먼저 build_offline_wheels.ps1 을 실행하세요."
    exit 1
}

& $gh auth status 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "GitHub CLI 로그인이 필요합니다. 브라우저가 열리면 로그인하세요."
    & $gh auth login -h github.com -p https -w
}

# Release가 없으면 태그 기준으로 생성
& $gh release view $Tag 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating release $Tag ..."
    & $gh release create $Tag --title $Tag --notes @"
## Offline wheels

Attach ``wheels-win-amd64-py312.zip`` for Windows x64 + Python 3.12.

See ``docs/offline_setup.md``.
"@ --target main
}

Write-Host "Uploading $zip to $Tag ..."
& $gh release upload $Tag $zip --clobber
Write-Host "Done. Open: https://github.com/lky9464/LocalSubsidies_SupervisedLearning/releases/tag/$Tag"
