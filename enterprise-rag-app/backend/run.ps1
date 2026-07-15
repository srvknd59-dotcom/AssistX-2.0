# Starts the FastAPI backend on http://localhost:8000
# Run .\setup.ps1 first (once).
# If PowerShell says this script "is not digitally signed", run once from
# the enterprise-rag-app folder: Get-ChildItem -Recurse -Filter *.ps1 | Unblock-File

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
. .\.venv\Scripts\Activate.ps1

if (-not (Test-Path ".env")) {
    Write-Host "No .env found. Run .\setup.ps1 first."
    exit 1
}

uvicorn app.main:app --reload --port 8000
