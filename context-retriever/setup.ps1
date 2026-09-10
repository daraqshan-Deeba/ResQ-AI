# ResQ AI — Context Retriever bootstrap (Windows)
# Requires: Python 3.12+, Redis Cloud account with Context Retriever enabled

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "==> Installing context-surfaces (Python 3.12)..." -ForegroundColor Cyan
py -3.12 -m pip install -r requirements.txt

$Ctxctl = Join-Path $env:LOCALAPPDATA "Packages\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\LocalCache\local-packages\Python312\Scripts\ctxctl.exe"
if (-not (Test-Path $Ctxctl)) {
    $Ctxctl = (Get-Command ctxctl -ErrorAction SilentlyContinue).Source
}
if (-not $Ctxctl) {
    Write-Host "ctxctl not found on PATH. Install finished — locate ctxctl.exe in your Python 3.12 Scripts folder." -ForegroundColor Yellow
    exit 1
}

Write-Host "==> Validating models.py..." -ForegroundColor Cyan
py -3.12 -c "from models import CommunityReport, Shelter, SosEvent; print('models OK')"

Write-Host ""
Write-Host "Next steps (manual — requires Redis Cloud login):" -ForegroundColor Green
Write-Host "  1. & '$Ctxctl' auth login --username you@example.com"
Write-Host "  2. Set REDIS_PASSWORD, then create surface:"
Write-Host "     & '$Ctxctl' surface create --name 'ResQ AI Surface' --models ./models.py --redis-addr redis.example.com:6379 --redis-password `$env:REDIS_PASSWORD"
Write-Host "  3. & '$Ctxctl' agent create --surface-id <SURFACE_ID> --name 'ResQ Agent'"
Write-Host "  4. & '$Ctxctl' tools list --agent-key <AGENT_KEY>"
