$ErrorActionPreference = "Stop"

Set-Location "C:\predarb-framework\backend"

$connection = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($connection) {
    throw "A porta 8000 ja esta ocupada pelo PID $($connection.OwningProcess)."
}

$env:MOCK_CONNECTOR_ENABLED = "true"
$env:HYPERLIQUID_CONNECTOR_ENABLED = "false"
$env:INITIAL_MARKET_SYNC_ENABLED = "false"
$env:SCHEDULER_ENABLED = "false"
$env:EXECUTION_WORKER_ENABLED = "false"
$env:ROUTER_DASHBOARD_ENABLED = "false"

$env:AI_ENABLED = "true"
$env:AI_PIPELINE_ENABLED = "true"
$env:AI_ADVISORY_ONLY = "true"
$env:AI_EXECUTION_AUTHORIZED = "false"
$env:AI_AUTO_LOAD_MODEL = "false"

$env:PAPER_ACCOUNT_ENABLED = "true"
$env:PAPER_ACCOUNT_AUTO_LOAD = "true"
$env:PAPER_ACCOUNT_AUTO_SAVE = "true"
$env:PAPER_ACCOUNT_PATH = "paper_data/phase5_server_account.json"
$env:PAPER_INITIAL_BALANCE = "10000"
$env:DATABASE_URL = "sqlite:///predarb_real_test_phase5_server.db"

Write-Host "PREDARB - FASE 5 / CONTA PAPER PERSISTENTE" -ForegroundColor Cyan
Write-Host "Paper path: $env:PAPER_ACCOUNT_PATH"
Write-Host "Paper enabled: $env:PAPER_ACCOUNT_ENABLED"
Write-Host "Execution worker: $env:EXECUTION_WORKER_ENABLED"
Write-Host "AI execution: $env:AI_EXECUTION_AUTHORIZED"

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level info
