# Starts the FastAPI backend on http://localhost:8000
# Run .\setup.ps1 first (once).

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
. .\.venv\Scripts\Activate.ps1

if (-not (Test-Path ".env")) {
    Write-Host "No .env found. Run .\setup.ps1 first."
    exit 1
}

uvicorn app.main:app --reload --port 8000
