@echo off
REM start-dev.bat — start development services on Windows (Command Prompt).
REM Each service opens in its own window.  Close each window to stop it.

setlocal

set VENV_DIR=.venv
set PYEXE=%VENV_DIR%\Scripts\python.exe
set CELERY=%VENV_DIR%\Scripts\celery.exe

if not exist "%PYEXE%" (
    echo Virtual environment not found. Run scripts\setup.bat first.
    exit /b 1
)

set DJANGO_SETTINGS_MODULE=config.settings.local

REM Load .env (basic key=value parsing)
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
        set "line=%%A"
        if not "!line:~0,1!"=="#" (
            set "%%A=%%B"
        )
    )
)

echo Starting NHWZ development services ...

REM ── Django ────────────────────────────────────────────────────────────────
start "NHWZ-Django" cmd /k "cd /d "%CD%\backend" && set DJANGO_SETTINGS_MODULE=config.settings.local && "%PYEXE%" manage.py runserver 0.0.0.0:8000"
echo   Django     -^> http://localhost:8000

REM ── Celery worker ─────────────────────────────────────────────────────────
start "NHWZ-Celery-Worker" cmd /k "cd /d "%CD%\backend" && set DJANGO_SETTINGS_MODULE=config.settings.local && "%CELERY%" -A config.celery worker --loglevel=warning --concurrency=2 --pool=solo"
echo   Celery     -^> worker started

REM ── Celery beat ───────────────────────────────────────────────────────────
start "NHWZ-Celery-Beat" cmd /k "cd /d "%CD%\backend" && set DJANGO_SETTINGS_MODULE=config.settings.local && "%CELERY%" -A config.celery beat --loglevel=warning"
echo   Celery     -^> beat started

REM ── Vite dev server ───────────────────────────────────────────────────────
if exist "frontend\node_modules" (
    start "NHWZ-Frontend" cmd /k "cd /d "%CD%\frontend" && npm run dev"
    echo   Frontend   -^> http://localhost:5173
) else (
    echo   Frontend   -^> skipped ^(run: cd frontend ^& npm ci ^& npm run dev^)
)

echo.
echo All services started. Close each window to stop a service.
endlocal
