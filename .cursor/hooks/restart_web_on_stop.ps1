# stop: pending 있으면 RestartWeb 1회. 잠금으로 스킵 시 플래그는 유지해 다음 기회에 재시도
$ErrorActionPreference = "SilentlyContinue"
$log = Join-Path $PSScriptRoot "web_restart.log"

function Write-Log([string]$msg) {
    $line = "[{0}] stop {1}" -f (Get-Date).ToString("o"), $msg
    Add-Content -LiteralPath $log -Value $line -Encoding utf8
}

$Root = $env:CURSOR_PROJECT_DIR
if (-not $Root) {
    $Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

$flag = Join-Path $Root ".cursor\web_restart_pending"
$flagAlt = Join-Path $PSScriptRoot "..\web_restart_pending"
$lock = Join-Path $env:TEMP "lsl_restart_web.lock"

$hasFlag = (Test-Path -LiteralPath $flag) -or (Test-Path -LiteralPath $flagAlt)
if (-not $hasFlag) {
    Write-Log "no_pending root=$Root"
    exit 0
}

if (Test-Path -LiteralPath $lock) {
    $age = ((Get-Date) - (Get-Item -LiteralPath $lock).LastWriteTime).TotalSeconds
    if ($age -lt 25) {
        # 플래그 유지 → 잠금 해제 후 다음 stop/수동 재시작에서 처리
        Write-Log "skip_lock age=$([math]::Round($age,1))s (flag kept)"
        exit 0
    }
}

$restart = Join-Path $Root "RestartWeb.bat"
if (-not (Test-Path -LiteralPath $restart)) {
    Write-Log "missing RestartWeb.bat"
    exit 0
}

# 실제로 기동할 때만 플래그 제거
Remove-Item -LiteralPath $flag -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $flagAlt -Force -ErrorAction SilentlyContinue

try {
    Start-Process -FilePath $restart -WorkingDirectory $Root -WindowStyle Normal
    Write-Log "started RestartWeb.bat"
} catch {
    # 실패 시 플래그 복구
    New-Item -ItemType File -Force -Path $flag | Out-Null
    Write-Log "Start-Process failed: $($_.Exception.Message)"
}
exit 0
