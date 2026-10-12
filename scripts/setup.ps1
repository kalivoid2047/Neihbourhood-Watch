#Requires -Version 5.1
<#
.SYNOPSIS
    First-time environment setup for Windows (PowerShell).

.DESCRIPTION
    Creates a virtual environment, installs Python dependencies, copies .env,
    runs migrations, and optionally builds the frontend.

.PARAMETER Mode
    dev  — install dev dependencies, use local settings (default)
    prod — install prod/windows dependencies, use production settings

.PARAMETER Python
    Path to the Python executable to use.  Defaults to 'python'.

.PARAMETER VenvDir
    Path for the virtual environment directory.  Defaults to '.venv'.

.EXAMPLE
    .\scripts\setup.ps1
    .\scripts\setup.ps1 -Mode prod
    .\scripts\setup.ps1 -Python "C:\Python312\python.exe"
#>
param(
    [ValidateSet('dev','prod')]
    [string]$Mode    = 'dev',
    [string]$Python  = 'python',
    [string]$VenvDir = '.venv'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ── 0. Sanity checks ─────────────────────────────────────────────────────────
$null = Get-Command $Python -ErrorAction Stop
$pyVer = & $Python -c "import sys; print('%d.%d' % sys.version_info[:2])"
Write-Host "Using Python $pyVer"

$hasNode = $null -ne (Get-Command node -ErrorAction SilentlyContinue)
$hasNpm  = $null -ne (Get-Command npm  -ErrorAction SilentlyContinue)
if (-not $hasNpm) { Write-Warning "npm not found — frontend build will be skipped." }

# ── 1. Virtual environment ────────────────────────────────────────────────────
if (-not (Test-Path $VenvDir)) {
    Write-Host "Creating virtual environment in $VenvDir ..."
    & $Python -m venv $VenvDir
}

$pip    = Join-Path $VenvDir 'Scripts\pip.exe'
$python = Join-Path $VenvDir 'Scripts\python.exe'
& $pip install --upgrade pip --quiet

# ── 2. Python dependencies ────────────────────────────────────────────────────
$reqs = if ($Mode -eq 'prod') { 'requirements\windows.txt' } else { 'requirements\dev.txt' }
Write-Host "Installing $reqs ..."
& $pip install -r $reqs --quiet

# ── 3. Environment file ───────────────────────────────────────────────────────
if (-not (Test-Path '.env')) {
    Copy-Item '.env.example' '.env'
    Write-Host ""
    Write-Host "  Created .env from .env.example"
    Write-Host "  Edit .env and set DATABASE_URL, REDIS_URL, DJANGO_SECRET_KEY, etc."
    Write-Host ""
}

# ── 4. Database migrations ────────────────────────────────────────────────────
$settings = if ($Mode -eq 'prod') { 'config.settings.production' } else { 'config.settings.local' }
Write-Host "Running migrations (settings: $settings) ..."
Push-Location backend
& $python manage.py migrate "--settings=$settings"
& $python manage.py seed_roles "--settings=$settings"
Pop-Location

# ── 5. Static files (production only) ────────────────────────────────────────
if ($Mode -eq 'prod') {
    Write-Host "Collecting static files ..."
    Push-Location backend
    & $python manage.py collectstatic --noinput "--settings=$settings"
    Pop-Location
}

# ── 6. Frontend ───────────────────────────────────────────────────────────────
if ($hasNpm) {
    Write-Host "Installing frontend dependencies ..."
    Push-Location frontend
    & npm ci --silent
    if ($Mode -eq 'prod') {
        Write-Host "Building frontend ..."
        & npm run build
    }
    Pop-Location
}

Write-Host ""
Write-Host "Setup complete."
$startScript = if ($Mode -eq 'prod') { '.\scripts\start-prod.ps1' } else { '.\scripts\start-dev.ps1' }
Write-Host "  Start: $startScript"
