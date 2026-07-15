# Windows PowerShell setup script for the backend. No Docker required.
# Run from a PowerShell prompt: .\setup.ps1
# If PowerShell blocks the script, first run (once, as your user):
#   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
# If PowerShell says the script "is not digitally signed" (common right after
# extracting a downloaded ZIP - Windows flags those files), run once:
#   Get-ChildItem -Recurse -Filter *.ps1 | Unblock-File

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# This project needs Python 3.10+. Check what "py -3" resolves to before
# building a venv with it - an old Python here will fail in confusing ways
# much later (or silently produce a broken install), so catch it up front.
try {
    $pyVersionOutput = (& py -3 --version 2>&1 | Out-String).Trim()
} catch {
    $pyVersionOutput = ""
    $global:LASTEXITCODE = 1
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "Could not find Python via the 'py' launcher ('py' command not found or failed)."
    Write-Host "Install Python 3.10+ (64-bit) from https://python.org - check 'Add python.exe to PATH' on the first installer screen - then re-run .\setup.ps1"
    exit 1
}
if ($pyVersionOutput -match "Python (\d+)\.(\d+)") {
    $verMajor = [int]$Matches[1]
    $verMinor = [int]$Matches[2]
    if ($verMajor -lt 3 -or ($verMajor -eq 3 -and $verMinor -lt 10)) {
        Write-Host "Found $pyVersionOutput via 'py -3', but this project needs Python 3.10 or newer."
        Write-Host "Install a newer 64-bit Python from https://python.org (check 'Add python.exe to PATH'), then either:"
        Write-Host "  - re-run .\setup.ps1 (if the new version becomes the 'py -3' default), or"
        Write-Host "  - edit this file's 'py -3' below to the specific version, e.g. 'py -3.11'"
        exit 1
    }
}

# A venv is permanently bound to the interpreter that created it. If an old
# .venv from a previous (e.g. too-old-Python) attempt is still here, reusing
# it silently is exactly what caused a confusing, hard-to-diagnose failure
# before - so check it, and rebuild it automatically if it doesn't match.
function Test-VenvIsCompatible {
    param([string]$VenvPath)
    $cfgPath = Join-Path $VenvPath "pyvenv.cfg"
    if (-not (Test-Path $cfgPath)) { return $false }
    $cfgContent = Get-Content $cfgPath -Raw
    if ($cfgContent -match "version\s*=\s*(\d+)\.(\d+)") {
        $major = [int]$Matches[1]
        $minor = [int]$Matches[2]
        return ($major -gt 3 -or ($major -eq 3 -and $minor -ge 10))
    }
    return $false
}

if ((Test-Path ".venv") -and -not (Test-VenvIsCompatible ".venv")) {
    Write-Host "Found an existing .venv that isn't Python 3.10+ (or couldn't be verified) - removing it so it can be rebuilt cleanly..."
    Remove-Item -Recurse -Force ".venv"
}

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment using $pyVersionOutput ..."
    py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to create the virtual environment - see the error above."
        exit 1
    }
}

Write-Host "Activating virtual environment..."
. .\.venv\Scripts\Activate.ps1

# Deliberately NOT running "pip install --upgrade pip" here: on Windows, pip
# upgrading itself mid-run can corrupt the install if anything interrupts it
# (a locked file, a long path) - it's happened twice in testing. The pip that
# ships with a 3.10+ venv is new enough for everything in requirements.txt.
Write-Host "Installing dependencies (this can take a few minutes the first time)..."
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Dependency install failed - see the error above."
    Write-Host "A common cause on Windows is the project folder path being too long"
    Write-Host "(Windows has a ~260 character path limit). If your path is deeply"
    Write-Host "nested, move this whole project somewhere shorter, e.g. C:\rag-app\,"
    Write-Host "delete the .venv folder here, and re-run .\setup.ps1."
    exit 1
}

# Don't just trust the exit code - confirm the packages this app actually
# needs are really importable before declaring success.
python -c "import fastapi, elasticsearch, openai" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "pip reported success but key packages still aren't importable."
    Write-Host "Delete the .venv folder here and re-run .\setup.ps1."
    exit 1
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host ""
    Write-Host "Created .env - open it in Notepad and add your OPENAI_API_KEY, then run .\run.ps1"
    exit 1
}

Write-Host ""
Write-Host "Setup complete. Next: .\run.ps1"
