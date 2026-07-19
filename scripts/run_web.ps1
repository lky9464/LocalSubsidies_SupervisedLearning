# 로컬 전용 웹 UI (127.0.0.1 only)
# 사용: .\scripts\run_web.ps1  |  .\scripts\run_web.ps1 -Restart
param(
    [switch]$Restart
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

$py = Join-Path $Root ".venv\Scripts\python.exe"
$launcher = Join-Path $Root "scripts\_web_launcher.py"

if (-not (Test-Path $py)) {
    Write-Host "ERROR: .venv 없음."
    Write-Host "  python -m venv .venv"
    Write-Host "  .\.venv\Scripts\activate"
    Write-Host "  pip install -r requirements.txt"
    Read-Host "Enter 키를 누르면 종료"
    exit 1
}

& $py -c "import streamlit" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: streamlit 미설치."
    Read-Host "Enter 키를 누르면 종료"
    exit 1
}

function Open-Browser($readyLine) {
    if ($readyLine -match "^READY:(\d+)$") {
        $port = $Matches[1]
        $url = "http://127.0.0.1:$port"
        Write-Host ""
        Write-Host $url
        Start-Process $url
    }
}

if (-not $Restart) {
    $openOut = & $py $launcher open 2>$null
    if ($LASTEXITCODE -eq 0 -and $openOut) {
        Open-Browser ($openOut.Trim())
        Write-Host ""
        Write-Host "이미 실행 중입니다. 코드 반영: RestartWeb.bat 또는 -Restart"
        Read-Host "Enter 키를 누르면 종료"
        exit 0
    }
}

if ($Restart) {
    Write-Host "기존 Streamlit 종료 후 재시작..."
}

Write-Host ""
Write-Host "Starting Streamlit ..."
Write-Host "  (이 창을 닫으면 서버가 종료됩니다.)"
Write-Host ""

$ready = $null
$runArgs = @($launcher, "run")
if ($Restart) { $runArgs += "--restart" }

& $py @runArgs 2>&1 | ForEach-Object {
    $line = "$_"
    Write-Host $line
    if ($line -match "^READY:\d+$") { $script:ready = $line.Trim() }
}

if (-not $ready) {
    Write-Host "ERROR: Streamlit 시작 실패"
    Read-Host "Enter 키를 누르면 종료"
    exit 1
}

Open-Browser $ready
