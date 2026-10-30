$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendUrl = 'http://127.0.0.1:8000/api/health'
$frontendUrl = 'http://localhost:5173/'
$backendStdout = Join-Path $env:TEMP 'bis-assist-backend.log'
$backendStderr = Join-Path $env:TEMP 'bis-assist-backend-error.log'
$frontendStdout = Join-Path $env:TEMP 'bis-assist-frontend.log'
$frontendStderr = Join-Path $env:TEMP 'bis-assist-frontend-error.log'

function Test-LocalUrl([string]$Url) {
  try {
    Invoke-WebRequest -Uri $Url -TimeoutSec 2 -UseBasicParsing | Out-Null
    return $true
  } catch {
    return $false
  }
}

if (-not (Test-LocalUrl $backendUrl)) {
  Start-Process -FilePath 'python' `
    -ArgumentList @('-u', '-m', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', '8000') `
    -WorkingDirectory $projectRoot -WindowStyle Hidden `
    -RedirectStandardOutput $backendStdout -RedirectStandardError $backendStderr | Out-Null

  $backendReady = $false
  for ($attempt = 0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Seconds 1
    if (Test-LocalUrl $backendUrl) { $backendReady = $true; break }
  }
  if (-not $backendReady) {
    Write-Host 'Backend did not start. Check the backend log files in your Windows Temp folder.' -ForegroundColor Red
    exit 1
  }
}

if (-not (Test-LocalUrl $frontendUrl)) {
  Start-Process -FilePath 'node' `
    -ArgumentList @('node_modules/vite/bin/vite.js', '--host', 'localhost', '--port', '5173', '--strictPort') `
    -WorkingDirectory $projectRoot -WindowStyle Hidden `
    -RedirectStandardOutput $frontendStdout -RedirectStandardError $frontendStderr | Out-Null

  $frontendReady = $false
  for ($attempt = 0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Seconds 1
    if (Test-LocalUrl $frontendUrl) { $frontendReady = $true; break }
  }
  if (-not $frontendReady) {
    Write-Host 'Frontend did not start. Check the frontend log files in your Windows Temp folder.' -ForegroundColor Red
    exit 1
  }
}

Write-Host 'BIS Assist is ready at http://localhost:5173' -ForegroundColor Green
