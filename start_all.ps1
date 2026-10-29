# FoodCoach AI - PowerShell Master Launcher
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "   Starting FoodCoach AI Full-Stack Services" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

$root = $PSScriptRoot

Write-Host "[1/3] Launching Python FastAPI ML Service (Port 8000)..." -ForegroundColor Yellow
Start-Process cmd -ArgumentList "/k", "cd /d `"$root\ml_service`" && if exist .venv\Scripts\activate.bat (call .venv\Scripts\activate.bat) && python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload"

Start-Sleep -Seconds 3

Write-Host "[2/3] Launching Node.js Gateway (Port 5001)..." -ForegroundColor Yellow
Start-Process cmd -ArgumentList "/k", "cd /d `"$root\backend_gateway`" && npm start"

Start-Sleep -Seconds 2

Write-Host "[3/3] Launching React Vite Frontend (Port 5173)..." -ForegroundColor Yellow
Start-Process cmd -ArgumentList "/k", "cd /d `"$root\frontend_client`" && npm run dev"

Write-Host ""
Write-Host "===================================================" -ForegroundColor Green
Write-Host "  All 3 services are launching in separate windows!" -ForegroundColor Green
Write-Host "  - Frontend: http://localhost:5173" -ForegroundColor Cyan
Write-Host "  - Gateway:  http://localhost:5001" -ForegroundColor Cyan
Write-Host "  - ML Docs:  http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "  - Demo user: omkar.andhare@i2it.edu.in" -ForegroundColor Yellow
Write-Host "  - Password:  Password123" -ForegroundColor Yellow
Write-Host "===================================================" -ForegroundColor Green
