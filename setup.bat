@echo off
REM ===================================================================
REM  OrgMind - one-command setup for Windows
REM
REM  Checks your tools, creates a Python venv, installs Python and web
REM  dependencies, writes .env from the template, and reports whether
REM  FalkorDB is reachable. Safe to re-run.
REM
REM  Usage:  setup.bat
REM ===================================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo ==========================================================
echo   OrgMind setup
echo ==========================================================
echo.

set "FAILED=0"
set "WARNED=0"

REM ---------------------------------------------------------------- tools
echo [1/6] Checking required tools...

where git >nul 2>&1
if errorlevel 1 (
    echo   [X] git not found. Install from https://git-scm.com/downloads
    set "FAILED=1"
) else (
    for /f "delims=" %%v in ('git --version 2^>nul') do echo   [ok] %%v
)

REM `python` may be the Microsoft Store alias, which prints nothing useful.
set "PY="
for %%c in (python py python3) do (
    if not defined PY (
        %%c -c "import sys; print(sys.version_info[:2])" >nul 2>&1
        if not errorlevel 1 set "PY=%%c"
    )
)
if not defined PY (
    echo   [X] Python 3.11+ not found on PATH.
    echo       Install from https://www.python.org/downloads/
    echo       Windows: tick "Add python.exe to PATH" during install.
    echo       If `python` opens the Microsoft Store, disable the app
    echo       execution alias in Settings ^> Apps ^> Advanced app settings.
    set "FAILED=1"
) else (
    for /f "delims=" %%v in ('%PY% --version 2^>^&1') do echo   [ok] %%v
    %PY% -c "import sys; sys.exit(0 if sys.version_info[:2] >= (3,11) else 1)" >nul 2>&1
    if errorlevel 1 (
        echo   [X] Python 3.11 or newer is required.
        set "FAILED=1"
    )
)

where node >nul 2>&1
if errorlevel 1 (
    echo   [X] Node.js not found. Install from https://nodejs.org/
    set "FAILED=1"
) else (
    for /f "delims=" %%v in ('node --version 2^>nul') do echo   [ok] node %%v
)

where npm >nul 2>&1
if errorlevel 1 (
    echo   [X] npm not found ^(normally ships with Node.js^).
    set "FAILED=1"
) else (
    for /f "delims=" %%v in ('npm --version 2^>nul') do echo   [ok] npm %%v
)

if "%FAILED%"=="1" (
    echo.
    echo Setup cannot continue until the [X] items above are installed.
    echo See docs\SETUP.md for the full prerequisites table.
    echo.
    pause
    exit /b 1
)

REM ---------------------------------------------------------------- venv
echo.
echo [2/6] Creating the Python virtual environment...
if exist ".venv\Scripts\python.exe" (
    echo   [ok] .venv already exists
) else (
    %PY% -m venv .venv
    if errorlevel 1 (
        echo   [X] could not create .venv
        pause
        exit /b 1
    )
    echo   [ok] created .venv
)
set "VENV_PY=%CD%\.venv\Scripts\python.exe"

REM ---------------------------------------------------------------- python deps
echo.
echo [3/6] Installing Python dependencies...
echo       Core packages only - this takes well under a minute.
"%VENV_PY%" -m pip install --upgrade pip --quiet
"%VENV_PY%" -m pip install -e . --quiet
if errorlevel 1 (
    echo   [X] pip install failed. Scroll up for the reason.
    echo       A common cause on Windows is a very long path; try cloning
    echo       to something short like C:\dev\orgmind.
    pause
    exit /b 1
)
echo   [ok] core Python dependencies installed

REM Neural embeddings are optional and pull PyTorch (~2 GB, ~13 min).
echo.
echo   Optional: neural sentence embeddings give better semantic search.
echo   Without them the app uses a deterministic hashing embedding, so
echo   everything still works - ranking is just less precise.
set /p "WANT_ML=  Install them now? [y/N] "
if /i "%WANT_ML%"=="y" (
    echo   Installing sentence-transformers (this can take ~13 minutes)...
    "%VENV_PY%" -m pip install -e ".[ml]" --quiet
    if errorlevel 1 (
        echo   [!] that failed; continuing without them.
        echo       You can retry later: .venv\Scripts\python.exe -m pip install -e ".[ml]"
    ) else (
        echo   [ok] neural embeddings installed
    )
) else (
    echo   [ok] skipping; using the hashing embedding fallback
)

REM ---------------------------------------------------------------- web deps
echo.
echo [4/6] Installing web dependencies...
if exist "web\node_modules" (
    echo   [ok] web\node_modules already exists
) else (
    pushd web
    call npm install --no-audit --no-fund --loglevel=error
    if errorlevel 1 (
        echo   [X] npm install failed
        popd
        pause
        exit /b 1
    )
    popd
    echo   [ok] web dependencies installed
)

REM ---------------------------------------------------------------- .env
echo.
echo [5/6] Configuration...
if exist ".env" (
    echo   [ok] .env already exists - leaving it alone
) else (
    copy /y ".env.example" ".env" >nul
    echo   [ok] created .env from .env.example
    echo.
    echo   Optional, for a real LLM: put a Gemini key in .env
    echo       GEMINI_API_KEY=...      https://aistudio.google.com/apikey
    echo   Without one the agent runs demo mode - the graph and tools are
    echo   still real, only the planning is scripted.
)

REM ---------------------------------------------------------------- falkordb
echo.
echo [6/6] Checking the graph backend...
"%VENV_PY%" -m scripts.check_graph 2>nul
if errorlevel 1 (
    echo   [!] FalkorDB is not reachable.
    echo       That is fine: the app falls back to an in-memory graph seeded
    echo       from the synthetic data. To use the real database, see
    echo       docs\FALKORDB_SETUP.md ^(Docker or FalkorDB Cloud^).
    set "WARNED=1"
)

REM ---------------------------------------------------------------- done
echo.
echo ==========================================================
echo   Setup complete
echo ==========================================================
echo.
echo   Start the project:
echo       run.bat
echo.
echo   Then open:  http://localhost:3000
echo.
echo   Try asking:  Why did we choose Postgres over Mongo?
echo.
if "%WARNED%"=="1" (
    echo   Note: running without FalkorDB. The in-memory graph is seeded
    echo   automatically, so the demo questions still work.
    echo.
)
echo   Verify everything:
echo       .venv\Scripts\python.exe -m pytest tests\ -q
echo.
pause
endlocal
