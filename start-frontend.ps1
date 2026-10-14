# Start the Bhu-Darpan frontend (Windows PowerShell)
$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\Backend\webapp"

Write-Host "Starting static web server on http://localhost:8010" -ForegroundColor Green
python -m http.server 8010

