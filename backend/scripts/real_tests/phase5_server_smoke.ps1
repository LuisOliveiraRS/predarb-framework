param(
    [string]$BaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"
$ReportDir = Join-Path (Get-Location) "real_test_reports"
$ReportPath = Join-Path $ReportDir "phase5_server_smoke_report.json"
$Checks = @()

function Add-Check {
    param([string]$Name, [string]$Status, $Details)
    $script:Checks += [PSCustomObject]@{
        name = $Name
        status = $Status
        details = $Details
    }
    Write-Host "[$Status] $Name"
}

try {
    $health = Invoke-RestMethod -Uri "$BaseUrl/health" -TimeoutSec 20
    if (-not $health.lifecycle.paper_account) { throw "Lifecycle paper_account nao esta ativo." }
    if ($health.paper.execution_authorized) { throw "Conta paper autorizou execucao live." }
    Add-Check "Health e seguranca" "PASS" $health.paper

    Invoke-RestMethod -Uri "$BaseUrl/paper/reset?confirm=RESET-PAPER&persist=true" -Method Post -TimeoutSec 20 | Out-Null
    Add-Check "Reset explicito" "PASS" @{ reset = $true }

    $yesId = "phase5-http-yes-$([guid]::NewGuid())"
    $noId = "phase5-http-no-$([guid]::NewGuid())"
    $executedAt = [DateTimeOffset]::UtcNow.ToString("o")
    $payload = @{
        execution_id = "phase5-http-$([guid]::NewGuid())"
        persist = $true
        orders = @(
            @{ id=$yesId; platform="Hyperliquid"; market="Phase 5 HTTP"; symbol="PHASE5"; side="BUY"; quantity=100; price=0.44; opportunity_id="phase5-http"; leg="YES"; mode="PAPER" },
            @{ id=$noId; platform="Phase5Control"; market="Phase 5 HTTP"; symbol="PHASE5"; side="BUY"; quantity=100; price=0.46; opportunity_id="phase5-http"; leg="NO"; mode="PAPER" }
        )
        reports = @(
            @{ order_id=$yesId; platform="Hyperliquid"; symbol="PHASE5"; leg="YES"; side="BUY"; status="FILLED"; average_price=0.44; filled_quantity=100; gross_notional=44; fee=0.044; mode="PAPER"; executed_at=$executedAt },
            @{ order_id=$noId; platform="Phase5Control"; symbol="PHASE5"; leg="NO"; side="BUY"; status="FILLED"; average_price=0.46; filled_quantity=100; gross_notional=46; fee=0.046; mode="PAPER"; executed_at=$executedAt }
        )
    }
    $commit = Invoke-RestMethod -Uri "$BaseUrl/paper/commit" -Method Post -ContentType "application/json" -Body ($payload | ConvertTo-Json -Depth 20) -TimeoutSec 20
    if ($commit.orders_committed -ne 2) { throw "A conta nao confirmou duas ordens." }
    Add-Check "Commit paper" "PASS" $commit

    $account = Invoke-RestMethod -Uri "$BaseUrl/paper/account" -TimeoutSec 20
    if ($account.trade_count -ne 2 -or $account.open_positions -ne 2) { throw "Estado paper inesperado apos commit." }
    if ([math]::Abs([double]$account.wallet.balance - 9909.91) -gt 0.000001) { throw "Cash paper inesperado." }
    Add-Check "Carteira e posicoes" "PASS" $account

    $prices = @{}
    foreach ($position in $account.positions) {
        if ($position.status -eq "OPEN") { $prices[$position.id] = 0.50 }
    }
    $markPayload = @{ prices=$prices; persist=$true } | ConvertTo-Json -Depth 10
    $marked = Invoke-RestMethod -Uri "$BaseUrl/paper/mark" -Method Post -ContentType "application/json" -Body $markPayload -TimeoutSec 20
    if ([math]::Abs([double]$marked.account.unrealized_pnl - 9.91) -gt 0.000001) { throw "PnL nao realizado inesperado." }
    Add-Check "Mark-to-market" "PASS" $marked.account

    foreach ($position in $marked.account.positions) {
        if ($position.status -ne "OPEN") { continue }
        $settlement = if ($position.leg -eq "YES") { 1.0 } else { 0.0 }
        $body = @{ settlement_price=$settlement; persist=$true } | ConvertTo-Json
        Invoke-RestMethod -Uri "$BaseUrl/paper/settle/$($position.id)" -Method Post -ContentType "application/json" -Body $body -TimeoutSec 20 | Out-Null
    }

    $final = Invoke-RestMethod -Uri "$BaseUrl/paper/account" -TimeoutSec 20
    if ($final.open_positions -ne 0 -or $final.closed_positions -ne 2) { throw "Liquidacao paper incompleta." }
    if ([math]::Abs([double]$final.realized_pnl - 9.91) -gt 0.000001) { throw "PnL realizado inesperado." }
    if ($final.execution_authorized) { throw "Conta paper autorizou live." }
    Add-Check "Liquidacao e PnL realizado" "PASS" $final

    try {
        Invoke-RestMethod -Uri "$BaseUrl/paper/commit" -Method Post -ContentType "application/json" -Body ($payload | ConvertTo-Json -Depth 20) -TimeoutSec 20 | Out-Null
        throw "Commit duplicado foi aceito."
    } catch {
        if ($_.Exception.Message -like "*Commit duplicado foi aceito*") { throw }
    }
    Add-Check "Idempotencia" "PASS" @{ duplicate_blocked = $true }

    $saved = Invoke-RestMethod -Uri "$BaseUrl/paper/save" -Method Post -TimeoutSec 20
    Add-Check "Persistencia explicita" "PASS" $saved

    New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null
    $summary = @{ passed = @($Checks | Where-Object status -eq "PASS").Count; failed = 0; total = $Checks.Count }
    @{ test="PredArb Phase 5 Server Smoke"; summary=$summary; checks=$Checks; finished_at=[DateTimeOffset]::UtcNow.ToString("o") } | ConvertTo-Json -Depth 30 | Set-Content -Path $ReportPath -Encoding UTF8
    Write-Host "Todos os testes HTTP da Fase 5 passaram." -ForegroundColor Green
    Write-Host "Relatorio: $ReportPath" -ForegroundColor Yellow
} catch {
    Add-Check "Falha" "FAIL" @{ error = $_.Exception.Message }
    New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null
    $summary = @{ passed = @($Checks | Where-Object status -eq "PASS").Count; failed = 1; total = $Checks.Count }
    @{ test="PredArb Phase 5 Server Smoke"; summary=$summary; checks=$Checks; finished_at=[DateTimeOffset]::UtcNow.ToString("o") } | ConvertTo-Json -Depth 30 | Set-Content -Path $ReportPath -Encoding UTF8
    Write-Host "[FAIL] $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Relatorio: $ReportPath" -ForegroundColor Yellow
    throw
}
