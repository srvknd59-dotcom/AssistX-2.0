# Launches the backend and frontend together, each in its own PowerShell window.
# Run .\backend\setup.ps1 and .\frontend\setup.ps1 once each before using this.

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

Write-Host "Starting backend (FastAPI + Chroma) on http://localhost:8000 ..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd `"$root\backend`"; .\run.ps1"

Start-Sleep -Seconds 3

Write-Host "Starting frontend (React) on http://localhost:5173 ..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd `"$root\frontend`"; .\run.ps1"

Write-Host ""
Write-Host "Two new PowerShell windows should have opened."
Write-Host "Backend docs: http://localhost:8000/docs"
Write-Host "App:          http://localhost:5173"
Write-Host "Close this window any time; the two app windows run independently."
