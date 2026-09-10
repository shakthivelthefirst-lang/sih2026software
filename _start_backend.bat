@echo off
title LANDNEXUS Backend :8001
echo.
echo  ===  LANDNEXUS BACKEND  ===
echo  Port : 8001
echo  CWD  : %~dp0
echo.
cd /d "%~dp0"
python -m uvicorn backend.main:app --reload --port 8001
echo.
echo  [ERROR] Backend exited. See messages above.
pause
