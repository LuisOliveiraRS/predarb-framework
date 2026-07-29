param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8000,
    [int]$MarketUpdateIntervalSeconds = 5
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$BackendRoot = (
    Resolve-Path (
        Join-Path $PSScriptRoot "..\.."
    )
).Path

Set-Location $BackendRoot

$ExistingConnection = Get-NetTCPConnection `
    -LocalPort $Port `
    -State Listen `
    -ErrorAction SilentlyContinue |
    Select-Object -First 1

if ($ExistingConnection) {
    $Process = Get-CimInstance Win32_Process `
        -Filter "ProcessId = $($ExistingConnection.OwningProcess)" `
        -ErrorAction SilentlyContinue

    $CommandLine = if ($Process) {
        [string]$Process.CommandLine
    }
    else {
        "processo não identificado"
    }

    throw (
        "A porta $Port já está ocupada pelo PID " +
        "$($ExistingConnection.OwningProcess): $CommandLine. " +
        "Encerre o servidor anterior antes de iniciar a Fase 3."
    )
}

$env:MOCK_CONNECTOR_ENABLED = "true"
$env:HYPERLIQUID_CONNECTOR_ENABLED = "true"
$env:INITIAL_MARKET_SYNC_ENABLED = "true"

$env:SCHEDULER_ENABLED = "true"
$env:MARKET_UPDATE_INTERVAL_SECONDS = [string]$MarketUpdateIntervalSeconds

$env:EXECUTION_WORKER_ENABLED = "false"
$env:ROUTER_DASHBOARD_ENABLED = "false"

$env:AI_ENABLED = "true"
$env:AI_PIPELINE_ENABLED = "true"
$env:AI_STRICT_FEATURES = "false"
$env:AI_FAIL_ON_ERROR = "false"
$env:AI_ADVISORY_ONLY = "true"
$env:AI_EXECUTION_AUTHORIZED = "false"
$env:AI_AUTO_LOAD_MODEL = "false"

$env:DATABASE_URL = "sqlite:///predarb_real_test_phase3.db"

$env:HYPERLIQUID_API_URL = "https://api.hyperliquid.xyz"
$env:HYPERLIQUID_TIMEOUT_SECONDS = "15"
$env:HYPERLIQUID_MAX_RETRIES = "1"
$env:HYPERLIQUID_RETRY_DELAY_SECONDS = "0.5"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "PREDARB - FASE 3 / SERVIDOR CONTROLADO" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Backend:        $BackendRoot"
Write-Host "Mock:           $env:MOCK_CONNECTOR_ENABLED"
Write-Host "Hyperliquid:    $env:HYPERLIQUID_CONNECTOR_ENABLED"
Write-Host "Initial Sync:   $env:INITIAL_MARKET_SYNC_ENABLED"
Write-Host "Scheduler:      $env:SCHEDULER_ENABLED"
Write-Host "Intervalo:      $env:MARKET_UPDATE_INTERVAL_SECONDS s"
Write-Host "Worker:         $env:EXECUTION_WORKER_ENABLED"
Write-Host "AI Execution:   $env:AI_EXECUTION_AUTHORIZED"
Write-Host "URL:            http://${HostAddress}:$Port"
Write-Host ""

if (-not (Test-Path ".\app\main.py")) {
    throw "app\\main.py não foi encontrado em $BackendRoot."
}

& python -m uvicorn app.main:app `
    --host $HostAddress `
    --port $Port `
    --log-level info

exit $LASTEXITCODE
