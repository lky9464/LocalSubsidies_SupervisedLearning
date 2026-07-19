$ErrorActionPreference = "SilentlyContinue"
$inputJson = [Console]::In.ReadToEnd() | ConvertFrom-Json
$path = ($inputJson.file_path -replace '\\', '/').ToLower()

$patterns = @(
    '^app/',
    '^scripts/_web_launcher\.py$',
    '^scripts/_pick_web_port\.py$',
    '^scripts/run_web\.ps1$',
    '^runweb\.bat$',
    '^restartweb\.bat$',
    '^\.streamlit/'
)

foreach ($p in $patterns) {
    if ($path -match $p) {
        $flag = Join-Path $PSScriptRoot "..\web_restart_pending"
        New-Item -ItemType File -Force -Path $flag | Out-Null
        break
    }
}
exit 0
