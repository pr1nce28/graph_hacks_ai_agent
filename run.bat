@echo off
REM ===================================================================
REM  OrgMind - start the API and the web UI
REM
REM  Opens two windows: FastAPI on :8000 and Next.js on :3000.
REM  Run setup.bat first if you have not.
REM
REM  Usage:  run.bat
REM ===================================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo   The virtual environment is missing.
    echo   Run setup.bat first.
    echo.
    pause
    exit /b 1
)

if not exist "web\node_modules" (
    echo.
    echo   Web dependencies are missing.
    echo   Run setup.bat first, or:  cd web ^&^& npm install
    echo.
    pause
    exit /b 1
)

echo.
echo ==========================================================
echo   Starting OrgMind
echo ==========================================================
echo.
echo   API  -^>  http://localhost:8000
echo   Web  -^>  http://localhost:3000
echo.
echo   Two windows will open. Close them (or press Ctrl+C in each)
echo   to stop the servers.
echo.

REM Free the ports if a previous run is still holding them.
for %%P in (8000 3000) do (
    for /f "tokens=5" %%I in ('netstat -ano ^| findstr ":%%P " ^| findstr LISTENING') do (
        echo   freeing port %%P ^(pid %%I^)
        taskkill /PID %%I /F >nul 2>&1
    )
)

start "OrgMind API" cmd /k "cd /d "%~dp0" && .venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000"

REM Give the API a moment to bind before the UI starts.
timeout /t 4 /nobreak >nul

start "OrgMind Web" cmd /k "cd /d "%~dp0web" && npm run dev"

echo   Started. Waiting for the API to answer...
timeout /t 12 /nobreak >nul

.venv\Scripts\python.exe -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=5).status==200 else 1)" >nul 2>&1
if errorlevel 1 (
    echo.
    echo   [!] The API has not answered yet. Check the "OrgMind API" window
    echo       for errors - it may just need a few more seconds.
) else (
    echo   [ok] API is up
)

echo.
echo   Open  http://localhost:3000  in your browser.
echo.
echo   First question to try:
echo       Why did we choose Postgres over Mongo?
echo.
pause
endlocal
