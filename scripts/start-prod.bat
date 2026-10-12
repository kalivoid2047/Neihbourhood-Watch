@echo off
REM start-prod.bat — start NHWZ in production mode on Windows (waitress + Celery).
REM Each service opens in its own window.
REM
REM For unattended deployment, use NSSM to wrap each service as a Windows Service.
REM See DEPLOYMENT_GUIDE.md for instructions.

setlocal enabledelayedexpansion

set VENV_DIR=.venv
set PORT=%1
if "%PORT%"=="" set PORT=8000

set PYEXE=%VENV_DIR%\Scripts\python.exe
set CELERY=%VENV_DIR%\Scripts\celery.exe
set WAITRESS=%VENV_DIR%\Scripts\waitress-serve.exe

if not exist "%PYEXE%" (
    echo Virtual environment not found. Run scripts\setup.bat prod first.
    exit /b 1
)

REM Load .env
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
        set "line=%%A"
        if not "!line:~0,1!"=="#" (
            set "%%A=%%B"
        )
    )
)

set DJANGO_SETTINGS_MODULE=config.settings.production

REM Guard against placeholder secret key
if "%DJANGO_SECRET_KEY%"=="local-development-secret-key" (
    echo ERROR: DJANGO_SECRET_KEY is still the placeholder. Set it in .env
    exit /b 1
)
if "%DJANGO_SECRET_KEY%"=="" (
    echo ERROR: DJANGO_SECRET_KEY is not set. Set it in .env
    exit /b 1
)

echo Running pre-flight checks ...
pushd backend
"%PYEXE%" manage.py migrate --settings=config.settings.production --noinput
"%PYEXE%" manage.py collectstatic --noinput --settings=config.settings.production
popd

echo Starting NHWZ production services ...

REM ── waitress ──────────────────────────────────────────────────────────────
start "NHWZ-API" cmd /k "cd /d "%CD%\backend" && set DJANGO_SETTINGS_MODULE=config.settings.production && "%WAITRESS%" --port=%PORT% --threads=8 config.wsgi:application"
echo   API        -^> http://0.0.0.0:%PORT%  (waitress)

REM ── Celery worker ─────────────────────────────────────────────────────────
start "NHWZ-Celery-Worker" cmd /k "cd /d "%CD%\backend" && set DJANGO_SETTINGS_MODULE=config.settings.production && "%CELERY%" -A config.celery worker --loglevel=info --concurrency=4 --pool=solo"
echo   Celery     -^> worker

REM ── Celery beat ───────────────────────────────────────────────────────────
start "NHWZ-Celery-Beat" cmd /k "cd /d "%CD%\backend" && set DJANGO_SETTINGS_MODULE=config.settings.production && "%CELERY%" -A config.celery beat --loglevel=info"
echo   Celery     -^> beat

echo.
echo All services started.
echo NOTE: WebSocket (/ws/) requires daphne. See DEPLOYMENT_GUIDE.md.
endlocal
