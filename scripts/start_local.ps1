# SCOS Local Startup Script (No Docker required)
$ErrorActionPreference = "Stop"

Write-Host "Starting SCOS Local Environment..." -ForegroundColor Cyan

# 1. Start the FastAPI Backend (Port 8000)
Write-Host "Starting FastAPI Backend on port 8000..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; if (-not (Test-Path venv)) { python -m venv venv; .\venv\Scripts\activate; pip install -r requirements.txt } else { .\venv\Scripts\activate }; if (-not (Test-Path static\app)) { New-Item -ItemType Directory -Force -Path static\app }; uvicorn main:app --host 127.0.0.1 --port 8000" -WindowStyle Normal

Write-Host "FastAPI Backend is spinning up in a new window." -ForegroundColor Green
Write-Host "Please wait a few seconds for initialization, then access the SCOS Web App at http://127.0.0.1:8000/app/index.html (or http://127.0.0.1:8000/)" -ForegroundColor White
Write-Host "Note: Database seeder is not executed automatically. To seed sample data for development, run: python backend/seed_db.py" -ForegroundColor DarkGray
