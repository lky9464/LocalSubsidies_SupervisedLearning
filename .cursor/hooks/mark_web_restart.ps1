# afterFileEdit: UI 관련 파일이면 pending 플래그 설정
# ConvertFrom-Json 은 edits 본문이 크면 실패할 수 있어 file_path 만 정규식으로 추출
$ErrorActionPreference = "SilentlyContinue"
$log = Join-Path $PSScriptRoot "web_restart.log"

function Write-Log([string]$msg) {
    $line = "[{0}] mark {1}" -f (Get-Date).ToString("o"), $msg
    Add-Content -LiteralPath $log -Value $line -Encoding utf8
}

try {
    $stdin = [Console]::In.ReadToEnd()
} catch {
    Write-Log "stdin_read_fail"
    exit 0
}

$filePath = $null
if ($stdin -match '"file_path"\s*:\s*"((?:\\.|[^"\\])*)"') {
    $filePath = $Matches[1] -replace '\\/', '/' -replace '\\\\', '\'
}
if (-not $filePath) {
    Write-Log "no_file_path"
    exit 0
}

$Root = $env:CURSOR_PROJECT_DIR
if (-not $Root) {
    $Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

$norm = ($filePath -replace '\\', '/').ToLowerInvariant()
$rootNorm = ($Root -replace '\\', '/').TrimEnd('/').ToLowerInvariant() + '/'

$rel = $norm
if ($norm.StartsWith($rootNorm)) {
    $rel = $norm.Substring($rootNorm.Length)
}

$patterns = @(
    '^api/',
    '^web/',
    '^scripts/_next_web_launcher\.py$',
    '^scripts/_restart_web_guard\.ps1$',
    '^runwebnext\.bat$',
    '^restartweb\.bat$'
)

$matched = $false
foreach ($p in $patterns) {
    if ($rel -match $p) {
        $matched = $true
        break
    }
}

if (-not $matched) {
    Write-Log "skip rel=$rel"
    exit 0
}

$flag = Join-Path $Root ".cursor\web_restart_pending"
# Join-Path PSScriptRoot 로도 동일 위치 보장
$flagAlt = Join-Path $PSScriptRoot "..\web_restart_pending"
New-Item -ItemType File -Force -Path $flag | Out-Null
New-Item -ItemType File -Force -Path $flagAlt | Out-Null
Write-Log "pending set rel=$rel"
exit 0
