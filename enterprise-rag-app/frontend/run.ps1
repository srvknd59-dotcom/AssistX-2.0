# Starts the React dev server on http://localhost:5173
# Run .\setup.ps1 first (once).
# If PowerShell says this script "is not digitally signed", run once from
# the enterprise-rag-app folder: Get-ChildItem -Recurse -Filter *.ps1 | Unblock-File

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
npm run dev
