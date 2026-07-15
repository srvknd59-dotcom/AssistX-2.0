# Launches the backend and frontend together, each in its own PowerShell window.
# Run .\backend\setup.ps1 and .\frontend\setup.ps1 once each before using this.
# Elasticsearch must already be running (see backend/README_ELASTICSEARCH.md) -
# this script does not start it.
# If PowerShell says any script here "is not digitally signed" (common right
# after extracting a downloaded ZIP - Windows flags those files), run once:
#   Get-ChildItem -Recurse -Filter *.ps1 | Unblock-File

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

Write-Host "Starting backend (FastAPI + Elasticsearch) on http://localhost:8000 ..."
Write-Host "(Elasticsearch itself must already be running separately - see backend/README_ELASTICSEARCH.md)"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd `"$root\backend`"; .\run.ps1"

Start-Sleep -Seconds 3

Write-Host "Starting frontend (React) on http://localhost:5173 ..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd `"$root\frontend`"; .\run.ps1"

Write-Host ""
Write-Host "Two new PowerShell windows should have opened."
Write-Host "Backend docs: http://localhost:8000/docs"
Write-Host "App:          http://localhost:5173"
Write-Host "Close this window any time; the two app windows run independently."
