#Requires -Version 5.1
<#
.SYNOPSIS
    Start NHWZ in production mode on Windows (waitress + Celery).

.DESCRIPTION
    Uses waitress (pure-Python WSGI server) for HTTP.  WebSocket support on
    Windows requires running daphne separately; see DEPLOYMENT_GUIDE.md.

    Each process is launched in its own cmd window so logs are visible.
    For unattended production use, configure each process as a Windows Service
    using NSSM (see DEPLOYMENT_GUIDE.md).

.PARAMETER VenvDir
    Path to the virtual environment.  Defaults to '.venv'.

.PARAMETER Port
    HTTP port for waitress.  Defaults to 8000.

.PARAMETER Threads
    Number of waitress threads.  Defaults to 8.
#>
param(
    [string]$VenvDir = '.venv',
    [int]   $Port    = 8000,
    [int]   $Threads = 8
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not (Test-Path $VenvDir)) {
    Write-Error "Virtual environment not found. Run .\scripts\setup.ps1 -Mode prod first."
    exit 1
}

$python  = Resolve-Path (Join-Path $VenvDir 'Scripts\python.exe')
$celery  = Resolve-Path (Join-Path $VenvDir 'Scripts\celery.exe')
$waitress = Resolve-Path (Join-Path $VenvDir 'Scripts\waitress-serve.exe')
$root    = $PWD.Path

# Load .env
if (Test-Path '.env') {
    Get-Content '.env' | Where-Object { $_ -match '^\s*[^#]' -and $_ -match '=' } | ForEach-Object {
        $parts = $_ -split '=', 2
        [System.Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim(), 'Process')
    }
}

$env:DJANGO_SETTINGS_MODULE = 'config.settings.production'

# Guard: refuse to start with placeholder secret key
$secretKey = [System.Environment]::GetEnvironmentVariable('DJANGO_SECRET_KEY', 'Process')
if (-not $secretKey -or $secretKey -eq 'local-development-secret-key') {
    Write-Error "DJANGO_SECRET_KEY is not set or is still the placeholder.`nGenerate one and set it in .env"
    exit 1
}

Write-Host "Running pre-flight checks ..."
Push-Location backend
& $python manage.py migrate --settings=config.settings.production --noinput
& $python manage.py collectstatic --noinput --settings=config.settings.production
Pop-Location

Write-Host "Starting NHWZ production services ..."

# ── waitress WSGI server ──────────────────────────────────────────────────────
Start-Process -FilePath 'cmd.exe' -ArgumentList "/k", `
    "title NHWZ-API && cd /d `"$root\backend`" && set DJANGO_SETTINGS_MODULE=config.settings.production && `"$waitress`" --port=$Port --threads=$Threads config.wsgi:application" `
    -WindowStyle Normal

Write-Host "  API        -> http://0.0.0.0:$Port  (waitress WSGI)"

# ── Celery worker ─────────────────────────────────────────────────────────────
Start-Process -FilePath 'cmd.exe' -ArgumentList "/k", `
    "title NHWZ-Celery-Worker && cd /d `"$root\backend`" && set DJANGO_SETTINGS_MODULE=config.settings.production && `"$celery`" -A config.celery worker --loglevel=info --concurrency=4 --pool=solo" `
    -WindowStyle Minimized

Write-Host "  Celery     -> worker (pool=solo)"

# ── Celery beat ───────────────────────────────────────────────────────────────
Start-Process -FilePath 'cmd.exe' -ArgumentList "/k", `
    "title NHWZ-Celery-Beat && cd /d `"$root\backend`" && set DJANGO_SETTINGS_MODULE=config.settings.production && `"$celery`" -A config.celery beat --loglevel=info" `
    -WindowStyle Minimized

Write-Host "  Celery     -> beat"
Write-Host ""
Write-Host "All services started."
Write-Host "NOTE: WebSocket (/ws/) is not served by waitress."
Write-Host "      Run daphne separately for WebSocket support (see DEPLOYMENT_GUIDE.md)."
