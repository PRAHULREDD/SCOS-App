# SCOS Local Startup Script (No Docker required)
$ErrorActionPreference = "Stop"

Write-Host "Starting SCOS Local Environment..." -ForegroundColor Cyan

# 1. Start the AI Engine (Port 8001)
Write-Host "Starting AI Engine on port 8001..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd ai; if (-not (Test-Path venv)) { python -m venv venv; .\venv\Scripts\activate; pip install -r requirements.txt } else { .\venv\Scripts\activate }; uvicorn main:app --host 127.0.0.1 --port 8001" -WindowStyle Normal

# 2. Start the FastAPI Backend (Port 8000)
Write-Host "Starting FastAPI Backend on port 8000..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; if (-not (Test-Path venv)) { python -m venv venv; .\venv\Scripts\activate; pip install -r requirements.txt } else { .\venv\Scripts\activate }; if (-not (Test-Path static\app)) { New-Item -ItemType Directory -Force -Path static\app }; if (-not (Test-Path static\portal)) { New-Item -ItemType Directory -Force -Path static\portal }; python seed_db.py; uvicorn main:app --host 127.0.0.1 --port 8000" -WindowStyle Normal

Write-Host "Backend servers are spinning up in new windows." -ForegroundColor Green
Write-Host "Please wait 10 seconds for them to initialize, then you can try logging in from the Flutter Web App." -ForegroundColor White
