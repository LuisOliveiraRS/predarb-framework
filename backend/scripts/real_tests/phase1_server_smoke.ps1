param(
    [string]$BaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"

function Test-Endpoint {
    param(
        [string]$Name,
        [string]$Method,
        [string]$Path
    )

    $uri = "$BaseUrl$Path"
    Write-Host "`n[$Name] $Method $uri" -ForegroundColor Cyan

    if ($Method -eq "POST") {
        $response = Invoke-RestMethod -Method Post -Uri $uri -TimeoutSec 20
    } else {
        $response = Invoke-RestMethod -Method Get -Uri $uri -TimeoutSec 20
    }

    $response | ConvertTo-Json -Depth 12
    return $response
}

$root = Test-Endpoint "Root" "GET" "/"
if ($root.status -ne "running") { throw "Root inválido." }

$health = Test-Endpoint "Health" "GET" "/health"
if ($health.status -ne "healthy") { throw "Aplicação não está saudável." }
if ($health.ai.execution_authorized -ne $false) { throw "AI autorizou execução." }

$connectors = Test-Endpoint "Connectors" "GET" "/connectors/"
if (@($connectors).Count -ne 1 -or $connectors[0] -ne "mock") {
    throw "Apenas o MockConnector deveria estar registrado."
}

$refresh = Test-Endpoint "Refresh" "POST" "/connectors/refresh"
if ($refresh.markets -ne 5) { throw "O refresh não retornou 5 mercados." }

$markets = Test-Endpoint "Markets" "GET" "/markets/"
if (@($markets).Count -ne 5) { throw "O MarketRepository não retornou 5 mercados." }

$opportunities = Test-Endpoint "Opportunities" "GET" "/opportunities/"
if (@($opportunities).Count -lt 1) { throw "Nenhuma oportunidade encontrada." }

$pipeline = Test-Endpoint "Pipeline" "GET" "/opportunities/pipeline"
if (-not $pipeline.pipelines.analysis) { throw "Pipeline analysis ausente." }
if (-not $pipeline.pipelines.paper) { throw "Pipeline paper ausente." }
if (-not $pipeline.pipelines.live) { throw "Pipeline live ausente." }

$dashboard = Test-Endpoint "Dashboard" "GET" "/dashboard/api/snapshot"
if ($dashboard.markets -ne 5) { throw "Dashboard não refletiu os 5 mercados." }

Write-Host "`nTodos os testes HTTP passaram." -ForegroundColor Green
