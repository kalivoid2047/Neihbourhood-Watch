# generate-nginx-conf.ps1
# Renders infra/nginx/default.conf.template into infra/nginx/generated/default.conf
# using NHWZ_* variables from .env (or from the environment).
#
# Usage (from repo root):
#   .\scripts\generate-nginx-conf.ps1
#
# Note: On Windows, nginx is uncommon. This script is provided for WSL or
# cross-platform consistency. Most Windows production deployments use IIS or
# a reverse proxy managed separately. See DEPLOYMENT_GUIDE.md for details.

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
$Template = Join-Path $RootDir "infra\nginx\default.conf.template"
$OutputDir = Join-Path $RootDir "infra\nginx\generated"
$Output = Join-Path $OutputDir "default.conf"

# Load .env if present (does not override existing env vars)
$EnvFile = Join-Path $RootDir ".env"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | Where-Object { $_ -notmatch '^\s*#' -and $_ -match '=' } | ForEach-Object {
        $parts = $_ -split '=', 2
        $key = $parts[0].Trim()
        $val = $parts[1].Trim()
        if (-not (Test-Path "Env:\$key")) {
            [System.Environment]::SetEnvironmentVariable($key, $val, "Process")
        }
    }
}

$apiHost = $env:NHWZ_API_HOST
$staticPath = $env:NHWZ_STATIC_PATH
$mediaPath = $env:NHWZ_MEDIA_PATH

if (-not $apiHost)   { throw "NHWZ_API_HOST is not set. Add it to .env" }
if (-not $staticPath) { throw "NHWZ_STATIC_PATH is not set. Add it to .env" }
if (-not $mediaPath)  { throw "NHWZ_MEDIA_PATH is not set. Add it to .env" }

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$content = Get-Content $Template -Raw
$content = $content -replace '\$\{NHWZ_API_HOST\}',   $apiHost
$content = $content -replace '\$\{NHWZ_STATIC_PATH\}', $staticPath
$content = $content -replace '\$\{NHWZ_MEDIA_PATH\}',  $mediaPath

Set-Content -Path $Output -Value $content -Encoding UTF8

Write-Host "Generated: $Output"
Write-Host ""
Write-Host "  NHWZ_API_HOST    = $apiHost"
Write-Host "  NHWZ_STATIC_PATH = $staticPath"
Write-Host "  NHWZ_MEDIA_PATH  = $mediaPath"
