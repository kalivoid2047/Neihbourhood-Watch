@echo off
REM setup.bat — first-time setup for Windows (Command Prompt).
REM For PowerShell users, prefer setup.ps1 instead.
REM
REM Usage:
REM   scripts\setup.bat           (development mode)
REM   scripts\setup.bat prod      (production mode)

setlocal enabledelayedexpansion

set MODE=%1
if "%MODE%"=="" set MODE=dev

set PYTHON=python
set VENV_DIR=.venv

REM ── 1. Virtual environment ────────────────────────────────────────────────
if not exist "%VENV_DIR%" (
    echo Creating virtual environment in %VENV_DIR% ...
    %PYTHON% -m venv %VENV_DIR%
    if errorlevel 1 ( echo ERROR: failed to create venv. Is Python installed? & exit /b 1 )
)

set PIP=%VENV_DIR%\Scripts\pip.exe
set PYEXE=%VENV_DIR%\Scripts\python.exe

%PIP% install --upgrade pip --quiet

REM ── 2. Dependencies ───────────────────────────────────────────────────────
if "%MODE%"=="prod" (
    set REQS=requirements\windows.txt
) else (
    set REQS=requirements\dev.txt
)
echo Installing %REQS% ...
%PIP% install -r %REQS% --quiet

REM ── 3. Environment file ───────────────────────────────────────────────────
if not exist ".env" (
    copy .env.example .env >nul
    echo Created .env from .env.example — edit it before starting.
)

REM ── 4. Migrations ─────────────────────────────────────────────────────────
if "%MODE%"=="prod" (
    set SETTINGS=config.settings.production
) else (
    set SETTINGS=config.settings.local
)

echo Running migrations ...
pushd backend
%PYEXE% manage.py migrate --settings=%SETTINGS%
%PYEXE% manage.py seed_roles --settings=%SETTINGS%
popd

REM ── 5. Static files (prod only) ───────────────────────────────────────────
if "%MODE%"=="prod" (
    echo Collecting static files ...
    pushd backend
    %PYEXE% manage.py collectstatic --noinput --settings=%SETTINGS%
    popd
)

REM ── 6. Frontend ───────────────────────────────────────────────────────────
where npm >nul 2>&1
if not errorlevel 1 (
    echo Installing frontend dependencies ...
    pushd frontend
    call npm ci --silent
    if "%MODE%"=="prod" (
        echo Building frontend ...
        call npm run build
    )
    popd
)

echo.
echo Setup complete.
if "%MODE%"=="prod" (
    echo   Start: scripts\start-prod.bat
) else (
    echo   Start: scripts\start-dev.bat
)
endlocal
