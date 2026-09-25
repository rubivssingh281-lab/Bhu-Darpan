# Start the Bhu-Darpan React frontend (Windows PowerShell)
$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\frontend"

if (-not (Test-Path ".\node_modules")) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
    npm install
}

Write-Host "Starting dev server on http://localhost:5173" -ForegroundColor Green
npm run dev
