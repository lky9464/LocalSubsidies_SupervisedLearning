$ErrorActionPreference = "SilentlyContinue"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$flag = Join-Path $Root ".cursor\web_restart_pending"

if (-not (Test-Path $flag)) {
    exit 0
}

Remove-Item $flag -Force -ErrorAction SilentlyContinue
$restart = Join-Path $Root "RestartWeb.bat"
if (Test-Path $restart) {
    Start-Process -FilePath $restart -WorkingDirectory $Root
}
exit 0
