param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$BackendRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $BackendRoot

$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listener) {
    throw "A porta $Port já está ocupada pelo processo $($listener.OwningProcess)."
}

$env:MOCK_CONNECTOR_ENABLED = "true"
$env:HYPERLIQUID_CONNECTOR_ENABLED = "true"
$env:INITIAL_MARKET_SYNC_ENABLED = "true"
$env:SCHEDULER_ENABLED = "true"
$env:MARKET_UPDATE_INTERVAL_SECONDS = "10"
$env:EXECUTION_WORKER_ENABLED = "false"
$env:ROUTER_DASHBOARD_ENABLED = "false"

$env:AI_ENABLED = "true"
$env:AI_PIPELINE_ENABLED = "true"
$env:AI_STRICT_FEATURES = "false"
$env:AI_FAIL_ON_ERROR = "false"
$env:AI_ADVISORY_ONLY = "true"
$env:AI_EXECUTION_AUTHORIZED = "false"
$env:AI_AUTO_LOAD_MODEL = "false"

$env:PAPER_ACCOUNT_ENABLED = "true"
$env:PAPER_ACCOUNT_AUTO_LOAD = "true"
$env:PAPER_ACCOUNT_AUTO_SAVE = "true"
$env:PAPER_ACCOUNT_PATH = "paper_data/phase7_paper_account.json"
$env:PAPER_INITIAL_BALANCE = "10000"

$env:PAPER_SESSION_ENABLED = "true"
$env:PAPER_SESSION_AUTO_START = "false"
$env:PAPER_SESSION_AUTO_LOAD_REPORT = "true"
$env:PAPER_SESSION_INTERVAL_SECONDS = "10"
$env:PAPER_SESSION_STAKE_AMOUNT = "250"
$env:PAPER_SESSION_MAX_OPPORTUNITIES_PER_CYCLE = "1"
$env:PAPER_SESSION_FEE_RATE = "0.001"
$env:PAPER_SESSION_REPORT_PATH = "paper_data/phase7_paper_session_report.json"

$env:PAPER_RISK_ENABLED = "true"
$env:PAPER_RISK_MAX_TRADE_NOTIONAL = "500"
$env:PAPER_RISK_MAX_TOTAL_EXPOSURE = "2500"
$env:PAPER_RISK_MAX_MARKET_EXPOSURE = "300"
$env:PAPER_RISK_MAX_OPEN_POSITIONS = "10"
$env:PAPER_RISK_MAX_DAILY_TRADES = "20"
$env:PAPER_RISK_DAILY_LOSS_LIMIT = "500"
$env:PAPER_RISK_MAX_DRAWDOWN_RATE = "0.10"
$env:PAPER_RISK_MIN_ROI = "0"
$env:PAPER_RISK_MIN_CONFIDENCE = "0"
$env:PAPER_RISK_MAX_RISK_SCORE = "100"

$env:DATABASE_URL = "sqlite:///predarb_real_test_phase7.db"
$env:HYPERLIQUID_API_URL = "https://api.hyperliquid.xyz"
$env:HYPERLIQUID_TIMEOUT_SECONDS = "15"
$env:HYPERLIQUID_MAX_RETRIES = "1"
$env:HYPERLIQUID_RETRY_DELAY_SECONDS = "0.5"

Write-Host "PREDARB - FASE 7 / SESSÃO PAPER COM RISCO" -ForegroundColor Cyan
Write-Host "Backend:          $BackendRoot"
Write-Host "Mock:             $env:MOCK_CONNECTOR_ENABLED"
Write-Host "Hyperliquid:      $env:HYPERLIQUID_CONNECTOR_ENABLED"
Write-Host "Scheduler:        $env:SCHEDULER_ENABLED"
Write-Host "Paper Session:    $env:PAPER_SESSION_ENABLED"
Write-Host "Auto Start:       $env:PAPER_SESSION_AUTO_START"
Write-Host "Stake por ciclo:  R$ $env:PAPER_SESSION_STAKE_AMOUNT"
Write-Host "Worker live:      $env:EXECUTION_WORKER_ENABLED"
Write-Host "AI Execution:     $env:AI_EXECUTION_AUTHORIZED"
Write-Host

python -m uvicorn app.main:app --host 127.0.0.1 --port $Port --log-level info
