# Windows PowerShell setup for the React frontend. No Docker required.
# Requires Node.js 18+ (https://nodejs.org). Run from PowerShell: .\setup.ps1
# If PowerShell says this script "is not digitally signed", run once from
# the enterprise-rag-app folder: Get-ChildItem -Recurse -Filter *.ps1 | Unblock-File

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Installing frontend dependencies..."
npm install

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env with default VITE_API_BASE_URL=http://localhost:8000"
}

Write-Host ""
Write-Host "Setup complete. Next: .\run.ps1  (make sure the backend is already running)"
