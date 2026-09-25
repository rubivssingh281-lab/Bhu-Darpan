# Start the Bhu-Darpan FastAPI backend (Windows PowerShell)
$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\Backend"

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment (Python 3.12)..." -ForegroundColor Cyan
    py -3.12 -m venv .venv 2>$null
    if (-not (Test-Path ".\.venv\Scripts\python.exe")) { python -m venv .venv }
    .\.venv\Scripts\python.exe -m pip install --upgrade pip
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
}

Write-Host "Starting API on http://localhost:8000  (docs: /docs)" -ForegroundColor Green
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
