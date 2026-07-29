$ErrorActionPreference = "Stop"

$Backend = "C:\predarb-framework\backend"
Set-Location $Backend

$connection = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($connection) {
    throw "A porta 8000 já está ocupada pelo processo $($connection.OwningProcess). Encerre o servidor anterior."
}

$env:MOCK_CONNECTOR_ENABLED = "true"
$env:HYPERLIQUID_CONNECTOR_ENABLED = "false"
$env:INITIAL_MARKET_SYNC_ENABLED = "true"
$env:SCHEDULER_ENABLED = "false"
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
$env:PAPER_ACCOUNT_PATH = "paper_data/phase6_paper_account.json"
$env:PAPER_INITIAL_BALANCE = "10000"
$env:DATABASE_URL = "sqlite:///predarb_real_test_phase6.db"

Write-Host "PREDARB - FASE 6 / DASHBOARD PAPER" -ForegroundColor Cyan
Write-Host "Backend:          $Backend"
Write-Host "Mock:             $env:MOCK_CONNECTOR_ENABLED"
Write-Host "Hyperliquid:      $env:HYPERLIQUID_CONNECTOR_ENABLED"
Write-Host "Scheduler:        $env:SCHEDULER_ENABLED"
Write-Host "Execution Worker: $env:EXECUTION_WORKER_ENABLED"
Write-Host "Paper Account:    $env:PAPER_ACCOUNT_ENABLED"
Write-Host "Paper Path:       $env:PAPER_ACCOUNT_PATH"
Write-Host "AI Execution:     $env:AI_EXECUTION_AUTHORIZED"
Write-Host ""

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level info
