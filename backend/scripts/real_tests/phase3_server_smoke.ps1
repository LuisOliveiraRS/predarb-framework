param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [int]$ObservationSeconds = 18,
    [int]$PollSeconds = 2
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$BackendRoot = (
    Resolve-Path (
        Join-Path $PSScriptRoot "..\.."
    )
).Path

$ReportDirectory = Join-Path $BackendRoot "real_test_reports"
$ReportPath = Join-Path $ReportDirectory "phase3_server_smoke_report.json"

$StartedAt = [DateTimeOffset]::UtcNow
$Checks = [System.Collections.Generic.List[object]]::new()
$Notes = [System.Collections.Generic.List[string]]::new()

function Add-Check {
    param(
        [string]$Name,
        [object]$Details
    )

    $Checks.Add(
        [PSCustomObject]@{
            name = $Name
            status = "PASS"
            details = $Details
        }
    )

    Write-Host "[PASS] $Name" -ForegroundColor Green
}

function Add-Note {
    param([string]$Message)

    $Notes.Add($Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Assert-Condition {
    param(
        [bool]$Condition,
        [string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function Invoke-TestEndpoint {
    param(
        [string]$Name,
        [string]$Method,
        [string]$Path,
        [int]$TimeoutSec = 45
    )

    $Uri = "$BaseUrl$Path"
    Write-Host "`n[$Name] $Method $Uri" -ForegroundColor Cyan

    if ($Method -eq "POST") {
        $Response = Invoke-RestMethod `
            -Method Post `
            -Uri $Uri `
            -TimeoutSec $TimeoutSec
    }
    else {
        $Response = Invoke-RestMethod `
            -Method Get `
            -Uri $Uri `
            -TimeoutSec $TimeoutSec
    }

    ($Response | ConvertTo-Json -Depth 30) | Out-Host
    return $Response
}

function Get-ConsistentDashboardRepositorySample {
    param(
        [int]$Attempts = 8,
        [int]$DelayMilliseconds = 750
    )

    $LastSample = $null

    for ($Attempt = 1; $Attempt -le $Attempts; $Attempt++) {
        $Before = Invoke-RestMethod `
            -Method Get `
            -Uri "$BaseUrl/connectors/status" `
            -TimeoutSec 30

        $Dashboard = Invoke-RestMethod `
            -Method Get `
            -Uri "$BaseUrl/dashboard/api/snapshot?refresh=true" `
            -TimeoutSec 30

        $MarketsResponse = Invoke-RestMethod `
            -Method Get `
            -Uri "$BaseUrl/markets/" `
            -TimeoutSec 30

        $After = Invoke-RestMethod `
            -Method Get `
            -Uri "$BaseUrl/connectors/status" `
            -TimeoutSec 30

        $Markets = @($MarketsResponse)
        $DashboardDataMarkets = @($Dashboard.data.markets)

        $LastSample = [PSCustomObject]@{
            attempt = $Attempt
            dashboard = $Dashboard
            markets = $Markets
            dashboard_count = [int]$Dashboard.markets
            dashboard_data_count = $DashboardDataMarkets.Count
            repository_count = $Markets.Count
            status_repository_count = [int]$After.repository.markets
            before_updated_at = [string]$Before.repository.updated_at
            after_updated_at = [string]$After.repository.updated_at
        }

        if ($LastSample.dashboard_count -ne $LastSample.dashboard_data_count) {
            throw (
                "Dashboard internamente inconsistente: " +
                "markets=$($LastSample.dashboard_count), " +
                "data.markets=$($LastSample.dashboard_data_count)."
            )
        }

        $StableRepository = (
            $LastSample.before_updated_at -eq $LastSample.after_updated_at
        )

        $CountsMatch = (
            $LastSample.dashboard_count -eq $LastSample.repository_count -and
            $LastSample.repository_count -eq $LastSample.status_repository_count
        )

        if ($StableRepository -and $CountsMatch) {
            return $LastSample
        }

        Write-Host (
            "[WARN] Snapshot concorrente; nova tentativa $Attempt/$Attempts. " +
            "dashboard=$($LastSample.dashboard_count), " +
            "repository=$($LastSample.repository_count), " +
            "status=$($LastSample.status_repository_count), " +
            "before=$($LastSample.before_updated_at), " +
            "after=$($LastSample.after_updated_at)"
        ) -ForegroundColor Yellow

        Start-Sleep -Milliseconds $DelayMilliseconds
    }

    throw (
        "Dashboard divergiu do MarketRepository após $Attempts tentativas estáveis/concorrentes. " +
        "dashboard=$($LastSample.dashboard_count), " +
        "data.markets=$($LastSample.dashboard_data_count), " +
        "repository=$($LastSample.repository_count), " +
        "status=$($LastSample.status_repository_count), " +
        "before=$($LastSample.before_updated_at), " +
        "after=$($LastSample.after_updated_at)."
    )
}

function Get-MarketIdentity {
    param([object]$Market)

    $Connector = [string]$Market.connector
    $MarketId = [string]$Market.market_id

    $Connector = $Connector.Trim().ToLowerInvariant()
    $MarketId = $MarketId.Trim().ToLowerInvariant()

    if ($MarketId) {
        return "$Connector|market_id|$MarketId"
    }

    $Platform = ([string]$Market.platform).Trim().ToLowerInvariant()
    $Question = ([string]$Market.question).Trim().ToLowerInvariant()

    return "$Connector|$Platform|$Question"
}

function Assert-NoMarketDuplicates {
    param(
        [object[]]$Markets,
        [string]$Context
    )

    $Keys = @(
        $Markets |
            ForEach-Object {
                Get-MarketIdentity -Market $_
            }
    )

    $Duplicates = @(
        $Keys |
            Group-Object |
            Where-Object Count -gt 1
    )

    if ($Duplicates.Count -gt 0) {
        $Names = $Duplicates.Name -join ", "
        throw "Mercados duplicados em ${Context}: $Names"
    }
}

try {
    $Root = Invoke-TestEndpoint "Root" "GET" "/"
    Assert-Condition ($Root.status -eq "running") "Root inválido."
    Assert-Condition ($Root.ai.execution_authorized -eq $false) "AI autorizou execução."
    Add-Check "Aplicação raiz" $Root

    $Health = Invoke-TestEndpoint "Health" "GET" "/health"
    Assert-Condition ($Health.status -eq "healthy") "Aplicação não está saudável."
    Assert-Condition (-not $Health.startup_error) "Startup error: $($Health.startup_error)"
    Assert-Condition ($Health.connector_configuration.mock_enabled -eq $true) "MockConnector não está habilitado."
    Assert-Condition ($Health.connector_configuration.hyperliquid_enabled -eq $true) "HyperliquidConnector não está habilitado."
    Assert-Condition ($Health.lifecycle.scheduler -eq $true) "Scheduler não iniciou."
    Assert-Condition ($Health.lifecycle.execution_worker -eq $false) "Execution Worker deveria estar desligado."
    Assert-Condition ($Health.scheduler.enabled -eq $true) "Scheduler está desabilitado."
    Assert-Condition ($Health.scheduler.running -eq $true) "Scheduler está parado."
    Assert-Condition ($Health.scheduler.jobs -eq 1) "Quantidade de jobs inválida."
    Assert-Condition (@($Health.scheduler.job_ids).Count -eq 1) "IDs de jobs inválidos."
    Assert-Condition ([string](@($Health.scheduler.job_ids)[0]) -eq "market_update_task") "Job esperado não foi encontrado."
    Assert-Condition ($Health.ai.advisory_only -eq $true) "AI não está consultiva."
    Assert-Condition ($Health.ai.execution_authorized -eq $false) "AI autorizou execução."
    Add-Check "Lifecycle e scheduler" $Health

    $Connectors = Invoke-TestEndpoint "Connectors" "GET" "/connectors/"
    $ConnectorNames = @(
        $Connectors |
            ForEach-Object {
                ([string]$_).Trim().ToLowerInvariant()
            }
    )

    $ExpectedNames = @("hyperliquid", "mock")
    $ActualNames = @($ConnectorNames | Sort-Object -Unique)

    Assert-Condition ($ActualNames.Count -eq 2) "Deveriam existir exatamente dois connectors. Recebido: [$($ActualNames -join ', ')]"
    Assert-Condition (($ActualNames -join ",") -eq ($ExpectedNames -join ",")) "Connectors inesperados: [$($ActualNames -join ', ')]"

    $ConnectorHealth = Invoke-TestEndpoint "Connector Health" "GET" "/connectors/health"
    Assert-Condition ($ConnectorHealth.registered -eq 2) "Quantidade de connectors inválida."
    Assert-Condition ($ConnectorHealth.online -eq 2) "Um connector está offline."
    Assert-Condition ($ConnectorHealth.errors -eq 0) "Um connector retornou erro."
    Add-Check "Dois connectors online" ([PSCustomObject]@{
        names = $ActualNames
        health = $ConnectorHealth
    })

    $InitialMarketsResponse = Invoke-TestEndpoint "Initial Markets" "GET" "/markets/"
    $InitialMarkets = @($InitialMarketsResponse)
    Assert-Condition ($InitialMarkets.Count -ge 5) "Repository inicial possui menos de cinco mercados."
    Assert-NoMarketDuplicates -Markets $InitialMarkets -Context "snapshot inicial"

    $InitialMockCount = @(
        $InitialMarkets |
            Where-Object connector -eq "mock"
    ).Count

    $InitialHyperliquidCount = @(
        $InitialMarkets |
            Where-Object connector -eq "hyperliquid"
    ).Count

    Assert-Condition ($InitialMockCount -eq 5) "MockConnector deveria fornecer cinco mercados; recebeu $InitialMockCount."

    if ($InitialHyperliquidCount -eq 0) {
        Add-Note "Nenhum mercado HIP-4 ativo foi normalizado no snapshot inicial."
    }

    Add-Check "Repository inicial deduplicado" ([PSCustomObject]@{
        total = $InitialMarkets.Count
        mock = $InitialMockCount
        hyperliquid = $InitialHyperliquidCount
    })

    Write-Host "`nObservando o scheduler por $ObservationSeconds segundos..." -ForegroundColor Yellow

    $Observations = [System.Collections.Generic.List[object]]::new()
    $Deadline = [DateTimeOffset]::UtcNow.AddSeconds($ObservationSeconds)

    while ([DateTimeOffset]::UtcNow -lt $Deadline) {
        $Status = Invoke-RestMethod `
            -Method Get `
            -Uri "$BaseUrl/connectors/status" `
            -TimeoutSec 30

        $MarketsResponse = Invoke-RestMethod `
            -Method Get `
            -Uri "$BaseUrl/markets/" `
            -TimeoutSec 30

        $Markets = @($MarketsResponse)
        Assert-NoMarketDuplicates -Markets $Markets -Context "observação do scheduler"

        $Observations.Add(
            [PSCustomObject]@{
                observed_at = [DateTimeOffset]::UtcNow.ToString("o")
                repository_updated_at = [string]$Status.repository.updated_at
                market_count = $Markets.Count
                mock_markets = @($Markets | Where-Object connector -eq "mock").Count
                hyperliquid_markets = @($Markets | Where-Object connector -eq "hyperliquid").Count
                connectors = $Status.connectors
            }
        )

        Start-Sleep -Seconds $PollSeconds
    }

    $DistinctUpdates = @(
        $Observations |
            ForEach-Object repository_updated_at |
            Where-Object { $_ } |
            Sort-Object -Unique
    )

    Assert-Condition ($DistinctUpdates.Count -ge 2) "O repository.updated_at não avançou em pelo menos dois ciclos."

    $InvalidMockSnapshots = @(
        $Observations |
            Where-Object mock_markets -ne 5
    )

    Assert-Condition ($InvalidMockSnapshots.Count -eq 0) "O conjunto de mercados mock variou ou acumulou registros."

    $ConnectorErrors = [System.Collections.Generic.List[object]]::new()

    foreach ($Observation in $Observations) {
        foreach ($Property in $Observation.connectors.PSObject.Properties) {
            if ($Property.Value.error) {
                $ConnectorErrors.Add(
                    [PSCustomObject]@{
                        observed_at = $Observation.observed_at
                        connector = $Property.Name
                        error = [string]$Property.Value.error
                    }
                )
            }
        }
    }

    Assert-Condition ($ConnectorErrors.Count -eq 0) "Foram encontrados erros de connector durante a observação."

    Add-Check "Scheduler atualizou sem acúmulo" ([PSCustomObject]@{
        observation_seconds = $ObservationSeconds
        samples = $Observations.Count
        distinct_repository_updates = $DistinctUpdates.Count
        observations = $Observations
    })

    $RefreshSnapshots = [System.Collections.Generic.List[object]]::new()

    for ($Index = 1; $Index -le 2; $Index++) {
        $Refresh = Invoke-TestEndpoint "Manual Refresh $Index" "POST" "/connectors/refresh"
        Assert-Condition ($Refresh.status -eq "completed") "Refresh $Index não foi concluído."

        $MarketsResponse = Invoke-RestMethod `
            -Method Get `
            -Uri "$BaseUrl/markets/" `
            -TimeoutSec 30

        $Markets = @($MarketsResponse)
        Assert-NoMarketDuplicates -Markets $Markets -Context "refresh manual $Index"
        Assert-Condition ($Refresh.markets -eq $Markets.Count) "Refresh $Index divergiu do repository."
        Assert-Condition (@($Markets | Where-Object connector -eq "mock").Count -eq 5) "Refresh $Index alterou os cinco mercados mock."

        $RefreshSnapshots.Add(
            [PSCustomObject]@{
                refresh = $Index
                markets = $Markets.Count
                repository = $Refresh.repository
                connectors = $Refresh.connectors
            }
        )
    }

    Add-Check "Refresh repetido idempotente" $RefreshSnapshots

    $OpportunitiesResponse = Invoke-TestEndpoint "Opportunities" "GET" "/opportunities/"
    $Opportunities = @($OpportunitiesResponse)
    $RouteKeys = [System.Collections.Generic.List[string]]::new()
    $HyperliquidRoutes = 0

    foreach ($Opportunity in $Opportunities) {
        $Question = ([string]$Opportunity.question).Trim().ToLowerInvariant()
        $YesPlatform = ([string]$Opportunity.buy_yes_platform).Trim().ToLowerInvariant()
        $NoPlatform = ([string]$Opportunity.buy_no_platform).Trim().ToLowerInvariant()

        Assert-Condition ([bool]$YesPlatform) "Oportunidade sem buy_yes_platform."
        Assert-Condition ([bool]$NoPlatform) "Oportunidade sem buy_no_platform."
        Assert-Condition ($YesPlatform -ne $NoPlatform) "Oportunidade utiliza a mesma plataforma nas duas pernas."

        $RouteKeys.Add("$Question|$YesPlatform|$NoPlatform")

        if ($YesPlatform -eq "hyperliquid" -or $NoPlatform -eq "hyperliquid") {
            $HyperliquidRoutes++
        }

        if ($Opportunity.PSObject.Properties.Name -contains "ai_analysis") {
            if ($null -ne $Opportunity.ai_analysis) {
                Assert-Condition ($Opportunity.ai_analysis.execution_authorized -eq $false) "AI autorizou execução em oportunidade."
            }
        }
    }

    $DuplicateRoutes = @(
        $RouteKeys |
            Group-Object |
            Where-Object Count -gt 1
    )

    Assert-Condition ($DuplicateRoutes.Count -eq 0) "O comparator retornou rotas duplicadas."

    if ($Opportunities.Count -eq 0) {
        Add-Note "Nenhuma oportunidade foi aprovada neste snapshot."
    }
    elseif ($HyperliquidRoutes -eq 0) {
        Add-Note "Nenhuma oportunidade atual utiliza uma perna Hyperliquid."
    }

    $Pipeline = Invoke-TestEndpoint "Pipeline" "GET" "/opportunities/pipeline"
    Assert-Condition ($null -ne $Pipeline.pipelines.analysis) "Pipeline analysis ausente."
    Assert-Condition ($null -ne $Pipeline.pipelines.paper) "Pipeline paper ausente."
    Assert-Condition ($null -ne $Pipeline.pipelines.live) "Pipeline live ausente."

    Add-Check "Comparator e Pipeline" ([PSCustomObject]@{
        opportunities = $Opportunities.Count
        unique_routes = @($RouteKeys | Sort-Object -Unique).Count
        hyperliquid_routes = $HyperliquidRoutes
        pipeline = $Pipeline
    })

    Write-Host "`n[Dashboard Snapshot] GET consistente com repository" -ForegroundColor Cyan
    $DashboardSample = Get-ConsistentDashboardRepositorySample
    $Dashboard = $DashboardSample.dashboard

    ($Dashboard | ConvertTo-Json -Depth 30) | Out-Host

    Assert-Condition ($Dashboard.status -in @("ONLINE", "DEGRADED")) "Dashboard com status inválido."

    Add-Check "Dashboard consistente" ([PSCustomObject]@{
        dashboard = $Dashboard
        consistency = [PSCustomObject]@{
            attempt = $DashboardSample.attempt
            dashboard_count = $DashboardSample.dashboard_count
            dashboard_data_count = $DashboardSample.dashboard_data_count
            repository_count = $DashboardSample.repository_count
            status_repository_count = $DashboardSample.status_repository_count
            repository_updated_at = $DashboardSample.after_updated_at
        }
    })

    $FinishedAt = [DateTimeOffset]::UtcNow
    $Payload = [PSCustomObject]@{
        test = "PredArb Phase 3 - HTTP Scheduler Stability"
        started_at = $StartedAt.ToString("o")
        finished_at = $FinishedAt.ToString("o")
        duration_seconds = [Math]::Round(($FinishedAt - $StartedAt).TotalSeconds, 3)
        environment = [PSCustomObject]@{
            base_url = $BaseUrl
            observation_seconds = $ObservationSeconds
            poll_seconds = $PollSeconds
            mock_connector = $true
            hyperliquid_connector = $true
            scheduler = $true
            execution_worker = $false
            execution_authorized = $false
        }
        summary = [PSCustomObject]@{
            passed = $Checks.Count
            failed = 0
            warnings = $Notes.Count
        }
        notes = $Notes
        checks = $Checks
    }

    New-Item `
        -ItemType Directory `
        -Path $ReportDirectory `
        -Force |
        Out-Null

    $Payload |
        ConvertTo-Json -Depth 50 |
        Set-Content `
            -Path $ReportPath `
            -Encoding UTF8

    Write-Host "`n============================================================" -ForegroundColor Green
    Write-Host "PREDARB — FASE 3 / HTTP SCHEDULER E ESTABILIDADE" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "Aprovados: $($Checks.Count)"
    Write-Host "Falhas:    0"
    Write-Host "Avisos:    $($Notes.Count)"
    Write-Host "Relatório: $ReportPath"
    Write-Host "Execução live: bloqueada"
    Write-Host "`nTodos os testes HTTP da Fase 3 passaram." -ForegroundColor Green
}
catch {
    $FinishedAt = [DateTimeOffset]::UtcNow

    $Failure = [PSCustomObject]@{
        name = "Fase 3 HTTP"
        status = "FAIL"
        error = $_.Exception.Message
        script_stack_trace = $_.ScriptStackTrace
    }

    $Checks.Add($Failure)

    $Payload = [PSCustomObject]@{
        test = "PredArb Phase 3 - HTTP Scheduler Stability"
        started_at = $StartedAt.ToString("o")
        finished_at = $FinishedAt.ToString("o")
        duration_seconds = [Math]::Round(($FinishedAt - $StartedAt).TotalSeconds, 3)
        summary = [PSCustomObject]@{
            passed = @($Checks | Where-Object status -eq "PASS").Count
            failed = 1
            warnings = $Notes.Count
        }
        notes = $Notes
        checks = $Checks
    }

    New-Item `
        -ItemType Directory `
        -Path $ReportDirectory `
        -Force |
        Out-Null

    $Payload |
        ConvertTo-Json -Depth 50 |
        Set-Content `
            -Path $ReportPath `
            -Encoding UTF8

    Write-Host "`n[FAIL] $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Relatório: $ReportPath" -ForegroundColor Yellow
    throw
}
