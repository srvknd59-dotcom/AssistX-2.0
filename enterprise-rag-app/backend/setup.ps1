# Windows PowerShell setup script for the backend. No Docker required.
# Run from a PowerShell prompt: .\setup.ps1
# If PowerShell blocks the script, first run (once, as your user):
#   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    py -3 -m venv .venv
}

Write-Host "Activating virtual environment..."
. .\.venv\Scripts\Activate.ps1

Write-Host "Installing dependencies (this can take a few minutes the first time)..."
python -m pip install --upgrade pip
pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host ""
    Write-Host "Created .env - open it in Notepad and add your OPENAI_API_KEY, then run .\run.ps1"
    exit 1
}

Write-Host ""
Write-Host "Setup complete. Next: .\run.ps1"
