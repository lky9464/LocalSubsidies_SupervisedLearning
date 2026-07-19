# RestartWeb.bat 진입 가드: CreateNew 잠금 + 기존 RunWebNext 콘솔 종료 + pending 클리어
# exit 0 = 진행, exit 2 = 스킵(이미 재시작 중/직후)
$ErrorActionPreference = "SilentlyContinue"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$lock = Join-Path $env:TEMP "lsl_restart_web.lock"
$flag = Join-Path $Root ".cursor\web_restart_pending"

if (Test-Path -LiteralPath $lock) {
    $age = ((Get-Date) - (Get-Item -LiteralPath $lock).LastWriteTime).TotalSeconds
    if ($age -lt 25) {
        exit 2
    }
    Remove-Item -LiteralPath $lock -Force -ErrorAction SilentlyContinue
}

try {
    $fs = [System.IO.File]::Open(
        $lock,
        [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::None
    )
    $w = New-Object System.IO.StreamWriter($fs)
    $w.WriteLine((Get-Date).ToString("o"))
    $w.Dispose()
} catch {
    exit 2
}

if (Test-Path -LiteralPath $flag) {
    Remove-Item -LiteralPath $flag -Force -ErrorAction SilentlyContinue
}

# 기존 RunWebNext / 레거시 RunWeb 콘솔 종료 (새 창 기동 전)
Get-CimInstance Win32_Process -Filter "Name='cmd.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and ($_.CommandLine -match "RunWebNext\.bat|RunWeb\.bat") } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Get-Process -Name cmd -ErrorAction SilentlyContinue |
    Where-Object { $_.MainWindowTitle -like "*Local Subsidies Web UI*" } |
    ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }

exit 0
