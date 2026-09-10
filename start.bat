@echo off
setlocal
title LANDNEXUS Launcher

:: Resolve project root (strip trailing backslash from %%~dp0)
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

echo.
echo  ==========================================
echo   LANDNEXUS  -  Startup Launcher
echo  ==========================================
echo   Root    : %ROOT%
echo   Backend : http://localhost:8001
echo   Frontend: http://localhost:5173
echo  ==========================================
echo.

:: Kill anything already on 8001 or 5173 (leave 8000 alone for UNAR)
echo [CHECK] Clearing port 8001 ...
for /f "tokens=5" %%P in ('netstat -ano 2^>nul ^| findstr ":8001 " ^| findstr "LISTENING"') do (
    echo        PID %%P killed
    taskkill /PID %%P /F >nul 2>&1
)

echo [CHECK] Clearing port 5173 ...
for /f "tokens=5" %%P in ('netstat -ano 2^>nul ^| findstr ":5173 " ^| findstr "LISTENING"') do (
    echo        PID %%P killed
    taskkill /PID %%P /F >nul 2>&1
)
echo.

:: Launch backend helper in its own window
echo [1/3] Starting backend ...
start "LANDNEXUS Backend :8001" cmd /c "%ROOT%\_start_backend.bat"

:: Launch frontend helper in its own window
echo [2/3] Starting frontend ...
start "LANDNEXUS Frontend :5173" cmd /c "%ROOT%\frontend\_start_frontend.bat"

:: Wait up to 30 s for backend health
echo [3/3] Waiting for backend on port 8001 ...
set WAIT=0
:POLL
set /a WAIT+=1
if %WAIT% GTR 30 goto TIMEOUT
curl -s http://localhost:8001/health | findstr /C:"ok" >nul 2>&1
if errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto POLL
)
echo [OK]    Backend ready after %WAIT% second(s).
goto OPEN

:TIMEOUT
echo [WARN]  Backend not ready after 30 s - opening browser anyway.

:OPEN
echo.
echo [OPEN]  http://localhost:5173
start http://localhost:5173

echo.
echo  ==========================================
echo   LANDNEXUS is running
echo  ==========================================
echo   Backend  : http://localhost:8001
echo   Docs     : http://localhost:8001/docs
echo   Frontend : http://localhost:5173
echo  ==========================================
echo.
echo  Close this window - keep the two service windows open.
echo.
pause
endlocal
