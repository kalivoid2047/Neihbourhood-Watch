#Requires -Version 5.1
<#
.SYNOPSIS
    Start all NHWZ services for local development on Windows.

.DESCRIPTION
    Launches Django runserver, Celery worker, Celery beat, and the Vite dev
    server in separate windows.  Close this window or press Ctrl-C to stop
    Django; the other windows must be closed manually.

.PARAMETER VenvDir
    Path to the virtual environment.  Defaults to '.venv'.
#>
param(
    [string]$VenvDir = '.venv'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not (Test-Path $VenvDir)) {
    Write-Error "Virtual environment not found. Run .\scripts\setup.ps1 first."
    exit 1
}

$python = Resolve-Path (Join-Path $VenvDir 'Scripts\python.exe')
$celery = Resolve-Path (Join-Path $VenvDir 'Scripts\celery.exe')
$root   = $PWD.Path

# Load .env into the current session
if (Test-Path '.env') {
    Get-Content '.env' | Where-Object { $_ -match '^\s*[^#]' -and $_ -match '=' } | ForEach-Object {
        $parts = $_ -split '=', 2
        [System.Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim(), 'Process')
    }
}

$env:DJANGO_SETTINGS_MODULE = 'config.settings.local'

Write-Host "Starting NHWZ development services..."

# ── Django runserver ──────────────────────────────────────────────────────────
Start-Process -FilePath 'cmd.exe' -ArgumentList "/k", `
    "title NHWZ-Django && cd /d `"$root\backend`" && `"$python`" manage.py runserver 0.0.0.0:8000" `
    -WindowStyle Normal

Write-Host "  Django     -> http://localhost:8000"

# ── Celery worker ─────────────────────────────────────────────────────────────
Start-Process -FilePath 'cmd.exe' -ArgumentList "/k", `
    "title NHWZ-Celery-Worker && cd /d `"$root\backend`" && `"$celery`" -A config.celery worker --loglevel=warning --concurrency=2 --pool=solo" `
    -WindowStyle Minimized

Write-Host "  Celery     -> worker started (--pool=solo for Windows compatibility)"

# ── Celery beat ───────────────────────────────────────────────────────────────
Start-Process -FilePath 'cmd.exe' -ArgumentList "/k", `
    "title NHWZ-Celery-Beat && cd /d `"$root\backend`" && `"$celery`" -A config.celery beat --loglevel=warning" `
    -WindowStyle Minimized

Write-Host "  Celery     -> beat started"

# ── Vite dev server ───────────────────────────────────────────────────────────
$hasNpm = $null -ne (Get-Command npm -ErrorAction SilentlyContinue)
$frontendModules = Test-Path 'frontend\node_modules'

if ($hasNpm -and $frontendModules) {
    Start-Process -FilePath 'cmd.exe' -ArgumentList "/k", `
        "title NHWZ-Frontend && cd /d `"$root\frontend`" && npm run dev" `
        -WindowStyle Normal
    Write-Host "  Frontend   -> http://localhost:5173"
} else {
    Write-Host "  Frontend   -> skipped (run 'cd frontend; npm ci; npm run dev' manually)"
}

Write-Host ""
Write-Host "All services started in separate windows."
Write-Host "Close those windows (or Ctrl-C in each) to stop individual services."
