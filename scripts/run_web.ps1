# 로컬 전용 웹 UI (127.0.0.1 only)
# 사용 (권장):
#   powershell -ExecutionPolicy Bypass -File .\scripts\run_web.ps1
# 또는 프로젝트 루트 RunWeb.bat
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

$py = Join-Path $Root ".venv\Scripts\python.exe"
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
    Write-Host "ERROR: streamlit 미설치. 다음을 실행하세요:"
    Write-Host "  .\.venv\Scripts\activate"
    Write-Host "  pip install -r requirements.txt"
    Read-Host "Enter 키를 누르면 종료"
    exit 1
}

$pickScript = Join-Path $Root "scripts\_pick_web_port.py"
$port = (& $py $pickScript).Trim()
if (-not $port) {
    Write-Host "ERROR: 사용 가능한 포트(8501~8510)를 찾지 못했습니다."
    Read-Host "Enter 키를 누르면 종료"
    exit 1
}

$url = "http://127.0.0.1:$port"
try {
    $health = Invoke-WebRequest -Uri "$url/_stcore/health" -UseBasicParsing -TimeoutSec 2
    if ($health.StatusCode -eq 200 -and ($health.Content.Trim().ToLower() -eq "ok")) {
        Write-Host "이미 실행 중: $url"
        Start-Process $url
        Read-Host "Enter 키를 누르면 종료"
        exit 0
    }
} catch {
    # 신규 기동
}

Write-Host ""
Write-Host "Starting Streamlit ..."
Write-Host "  URL: $url"
Write-Host "  (이 창을 닫으면 서버가 종료됩니다.)"
Write-Host "  Do NOT use --server.address 0.0.0.0"
Write-Host ""

Start-Process $url
Start-Sleep -Seconds 2

try {
    & $py -m streamlit run (Join-Path $Root "app\main.py") `
        --server.address=127.0.0.1 `
        --server.port=$port `
        --browser.gatherUsageStats=false `
        --server.headless=true
}
catch {
    Write-Host "ERROR: $($_.Exception.Message)"
}
finally {
    Write-Host ""
    Write-Host "Streamlit 이 종료되었습니다."
    Read-Host "Enter 키를 누르면 창을 닫습니다"
}
