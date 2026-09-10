@echo off
title LANDNEXUS Frontend :5173
echo.
echo  ===  LANDNEXUS FRONTEND  ===
echo  Port : 5173
echo  CWD  : %~dp0
echo.
cd /d "%~dp0"
npm run dev
echo.
echo  [ERROR] Frontend exited. See messages above.
pause
