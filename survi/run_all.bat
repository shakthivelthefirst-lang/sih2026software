@echo off
setlocal
cd /d %~dp0
echo ==========================================
echo   SURVI LANDNEXUS - ONE CLICK START
echo ==========================================
echo [1/2] Preparing ML model...
python -m ml.train_model
if errorlevel 1 (
  echo ML preparation failed. Check Python dependencies.
  pause
  exit /b 1
)
echo [2/2] Starting backend...
start "SURVI Backend" cmd /k "cd /d %~dp0 && python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000"
timeout /t 3 /nobreak >nul
start "SURVI Frontend" cmd /k "cd /d %~dp0frontend && npm install && npm run dev -- --host 127.0.0.1"
timeout /t 5 /nobreak >nul
start "" "http://127.0.0.1:5173"
echo SURVI LANDNEXUS is starting.
