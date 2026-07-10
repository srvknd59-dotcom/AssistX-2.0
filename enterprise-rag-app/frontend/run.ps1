# Starts the React dev server on http://localhost:5173
# Run .\setup.ps1 first (once).

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
npm run dev
