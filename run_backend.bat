@echo off
title SURVI Backend
cd /d "%~dp0"
echo Starting FastAPI Backend...
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8001
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Backend failed to start.
    pause
)
