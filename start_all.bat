@echo off
title FoodCoach AI - Master Launcher
echo ===================================================
echo   Starting FoodCoach AI Full-Stack Services
echo ===================================================
echo.

echo [1/3] Launching Python FastAPI ML Service (Port 8000)...
start "FoodCoach - [1] ML Service (Port 8000)" cmd /k "cd ml_service && if exist .venv\Scripts\activate.bat (call .venv\Scripts\activate.bat) && python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload"

timeout /t 3 /nobreak >nul

echo [2/3] Launching Node.js Gateway (Port 5001)...
start "FoodCoach - [2] Node Gateway (Port 5001)" cmd /k "cd backend_gateway && npm start"

timeout /t 2 /nobreak >nul

echo [3/3] Launching React Vite Frontend (Port 5173)...
start "FoodCoach - [3] Frontend Client (Port 5173)" cmd /k "cd frontend_client && npm run dev"

echo.
echo ===================================================
echo   All 3 services are launching in separate windows!
echo   - Frontend: http://localhost:5173
echo   - Gateway:  http://localhost:5001
echo   - ML Docs:  http://localhost:8000/docs
echo   - Demo user: omkar.andhare@i2it.edu.in
echo   - Password:  Password123
echo ===================================================
pause
