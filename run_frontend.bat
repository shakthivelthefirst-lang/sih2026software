@echo off
title SURVI Frontend
cd /d "%~dp0frontend"
echo Starting Vite Frontend...
npm run dev
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Frontend failed to start.
    pause
)
