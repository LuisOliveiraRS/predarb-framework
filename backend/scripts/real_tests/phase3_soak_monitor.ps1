param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [int]$DurationSeconds = 120,
    [int]$PollSeconds = 5,
    [int]$MaxConsecutiveConnectorErrors = 3
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$BackendRoot = (
    Resolve-Path (
        Join-Path $PSScriptRoot "..\.."
    )
).Path

$ReportDirectory = Join-Path $BackendRoot "real_test_reports"
$ReportPath = Join-Path $ReportDirectory "phase3_soak_report.json"
$StartedAt = [DateTimeOffset]::UtcNow
$Deadline = $StartedAt.AddSeconds($DurationSeconds)
$Samples = [System.Collections.Generic.List[object]]::new()
$Notes = [System.Collections.Generic.List[string]]::new()
$ConsecutiveConnectorErrors = 0
$MaximumConsecutiveConnectorErrors = 0

function Assert-Condition {
    param(
        [bool]$Condition,
        [string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function Get-MarketIdentity {
    param([object]$Market)

    $Connector = ([string]$Market.connector).Trim().ToLowerInvariant()
    $MarketId = ([string]$Market.market_id).Trim().ToLowerInvariant()

    if ($MarketId) {
        return "$Connector|market_id|$MarketId"
    }

    $Platform = ([string]$Market.platform).Trim().ToLowerInvariant()
    $Question = ([string]$Market.question).Trim().ToLowerInvariant()
    return "$Connector|$Platform|$Question"
}

Write-Host "Monitorando $BaseUrl por $DurationSeconds segundos..." -ForegroundColor Cyan

try {
    while ([DateTimeOffset]::UtcNow -lt $Deadline) {
        $Health = Invoke-RestMethod `
            -Uri "$BaseUrl/health" `
            -Method Get `
            -TimeoutSec 30

        $Status = Invoke-RestMethod `
            -Uri "$BaseUrl/connectors/status" `
            -Method Get `
            -TimeoutSec 30

        $MarketsResponse = Invoke-RestMethod `
            -Uri "$BaseUrl/markets/" `
            -Method Get `
            -TimeoutSec 30

        $Markets = @($MarketsResponse)
        $Keys = @($Markets | ForEach-Object { Get-MarketIdentity -Market $_ })
        $DuplicateCount = @(
            $Keys |
                Group-Object |
                Where-Object Count -gt 1
        ).Count

        $Errors = [System.Collections.Generic.List[object]]::new()

        foreach ($Property in $Status.connectors.PSObject.Properties) {
            if ($Property.Value.error) {
                $Errors.Add(
                    [PSCustomObject]@{
                        connector = $Property.Name
                        error = [string]$Property.Value.error
                    }
                )
            }
        }

        if ($Errors.Count -gt 0) {
            $ConsecutiveConnectorErrors++
        }
        else {
            $ConsecutiveConnectorErrors = 0
        }

        if ($ConsecutiveConnectorErrors -gt $MaximumConsecutiveConnectorErrors) {
            $MaximumConsecutiveConnectorErrors = $ConsecutiveConnectorErrors
        }

        $Sample = [PSCustomObject]@{
            observed_at = [DateTimeOffset]::UtcNow.ToString("o")
            health = $Health.status
            startup_error = $Health.startup_error
            scheduler_running = $Health.scheduler.running
            scheduler_jobs = $Health.scheduler.jobs
            execution_worker = $Health.lifecycle.execution_worker
            ai_execution_authorized = $Health.ai.execution_authorized
            repository_updated_at = [string]$Status.repository.updated_at
            markets = $Markets.Count
            mock_markets = @($Markets | Where-Object connector -eq "mock").Count
            hyperliquid_markets = @($Markets | Where-Object connector -eq "hyperliquid").Count
            duplicate_markets = $DuplicateCount
            connector_errors = $Errors
        }

        $Samples.Add($Sample)

        Write-Host (
            "{0} | markets={1} mock={2} hyperliquid={3} duplicates={4} errors={5}" -f `
                $Sample.observed_at,
                $Sample.markets,
                $Sample.mock_markets,
                $Sample.hyperliquid_markets,
                $Sample.duplicate_markets,
                $Errors.Count
        )

        Start-Sleep -Seconds $PollSeconds
    }

    Assert-Condition ($Samples.Count -ge 2) "Poucas amostras foram coletadas."
    Assert-Condition (@($Samples | Where-Object health -ne "healthy").Count -eq 0) "A aplicação ficou não saudável durante o soak."
    Assert-Condition (@($Samples | Where-Object startup_error).Count -eq 0) "Foi registrado startup_error durante o soak."
    Assert-Condition (@($Samples | Where-Object scheduler_running -ne $true).Count -eq 0) "O scheduler parou durante o soak."
    Assert-Condition (@($Samples | Where-Object scheduler_jobs -ne 1).Count -eq 0) "A quantidade de jobs mudou durante o soak."
    Assert-Condition (@($Samples | Where-Object execution_worker -ne $false).Count -eq 0) "Execution Worker foi habilitado."
    Assert-Condition (@($Samples | Where-Object ai_execution_authorized -ne $false).Count -eq 0) "AI autorizou execução."
    Assert-Condition (@($Samples | Where-Object duplicate_markets -gt 0).Count -eq 0) "Foram detectados mercados duplicados."
    Assert-Condition (@($Samples | Where-Object mock_markets -ne 5).Count -eq 0) "Os cinco mercados mock não permaneceram estáveis."
    Assert-Condition ($MaximumConsecutiveConnectorErrors -lt $MaxConsecutiveConnectorErrors) "Connectors apresentaram erros consecutivos acima do limite."

    $DistinctUpdates = @(
        $Samples |
            ForEach-Object repository_updated_at |
            Where-Object { $_ } |
            Sort-Object -Unique
    )

    Assert-Condition ($DistinctUpdates.Count -ge 2) "O repository.updated_at não avançou durante o soak."

    $ErrorSamples = @(
        $Samples |
            Where-Object {
                @($_.connector_errors).Count -gt 0
            }
    )

    if ($ErrorSamples.Count -gt 0) {
        $Notes.Add("Ocorreram erros transitórios de connector, mas abaixo do limite consecutivo configurado.")
    }

    $FinishedAt = [DateTimeOffset]::UtcNow
    $Payload = [PSCustomObject]@{
        test = "PredArb Phase 3 - Soak Monitor"
        started_at = $StartedAt.ToString("o")
        finished_at = $FinishedAt.ToString("o")
        duration_seconds = [Math]::Round(($FinishedAt - $StartedAt).TotalSeconds, 3)
        environment = [PSCustomObject]@{
            base_url = $BaseUrl
            requested_duration_seconds = $DurationSeconds
            poll_seconds = $PollSeconds
            max_consecutive_connector_errors = $MaxConsecutiveConnectorErrors
        }
        summary = [PSCustomObject]@{
            status = "PASS"
            samples = $Samples.Count
            distinct_repository_updates = $DistinctUpdates.Count
            error_samples = $ErrorSamples.Count
            maximum_consecutive_connector_errors = $MaximumConsecutiveConnectorErrors
            warnings = $Notes.Count
        }
        notes = $Notes
        samples = $Samples
    }

    New-Item -ItemType Directory -Path $ReportDirectory -Force | Out-Null
    $Payload | ConvertTo-Json -Depth 50 | Set-Content -Path $ReportPath -Encoding UTF8

    Write-Host "`nSoak test aprovado." -ForegroundColor Green
    Write-Host "Amostras: $($Samples.Count)"
    Write-Host "Atualizações distintas: $($DistinctUpdates.Count)"
    Write-Host "Maior sequência de erros: $MaximumConsecutiveConnectorErrors"
    Write-Host "Relatório: $ReportPath"
}
catch {
    $FinishedAt = [DateTimeOffset]::UtcNow
    $Payload = [PSCustomObject]@{
        test = "PredArb Phase 3 - Soak Monitor"
        started_at = $StartedAt.ToString("o")
        finished_at = $FinishedAt.ToString("o")
        duration_seconds = [Math]::Round(($FinishedAt - $StartedAt).TotalSeconds, 3)
        summary = [PSCustomObject]@{
            status = "FAIL"
            samples = $Samples.Count
            maximum_consecutive_connector_errors = $MaximumConsecutiveConnectorErrors
            error = $_.Exception.Message
        }
        notes = $Notes
        samples = $Samples
    }

    New-Item -ItemType Directory -Path $ReportDirectory -Force | Out-Null
    $Payload | ConvertTo-Json -Depth 50 | Set-Content -Path $ReportPath -Encoding UTF8

    Write-Host "`nSoak test falhou: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Relatório: $ReportPath" -ForegroundColor Yellow
    throw
}
