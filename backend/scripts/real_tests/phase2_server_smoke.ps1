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
        $response = Invoke-RestMethod -Method Post -Uri $uri -TimeoutSec 45
    } else {
        $response = Invoke-RestMethod -Method Get -Uri $uri -TimeoutSec 45
    }

    # Exibe o JSON no host sem adicioná-lo ao pipeline de retorno da função.
    # Antes, ConvertTo-Json gerava uma segunda saída e contaminava variáveis
    # como $connectors, fazendo um único connector parecer dois resultados.
    ($response | ConvertTo-Json -Depth 20) | Out-Host

    return $response
}

$root = Test-Endpoint "Root" "GET" "/"
if ($root.status -ne "running") { throw "Root inválido." }
if ($root.ai.execution_authorized -ne $false) { throw "AI autorizou execução." }

$health = Test-Endpoint "Health" "GET" "/health"
if ($health.status -ne "healthy") { throw "Aplicação não está saudável." }
if ($health.startup_error) { throw "Startup error: $($health.startup_error)" }
if ($health.lifecycle.connectors -ne $true) { throw "Connectors não iniciaram." }
if ($health.lifecycle.scheduler -ne $false) { throw "Scheduler deveria estar desligado." }
if ($health.lifecycle.execution_worker -ne $false) { throw "Execution Worker deveria estar desligado." }
if ($health.ai.execution_authorized -ne $false) { throw "AI autorizou execução." }

$connectors = Test-Endpoint "Connectors" "GET" "/connectors/"
$connectorNames = @($connectors)

if (
    $connectorNames.Count -ne 1 -or
    [string]$connectorNames[0] -ne "hyperliquid"
) {
    $actual = $connectorNames -join ", "
    throw (
        "Apenas o HyperliquidConnector deveria estar registrado. " +
        "Recebido: [$actual]"
    )
}

$connectorHealth = Test-Endpoint "Connector Health" "GET" "/connectors/health"
if ($connectorHealth.registered -ne 1) { throw "Quantidade de connectors inválida." }
if ($connectorHealth.online -ne 1) { throw "Hyperliquid está offline." }
if ($connectorHealth.errors -ne 0) { throw "Hyperliquid retornou erro." }

$refresh = Test-Endpoint "Refresh" "POST" "/connectors/refresh"
if ($refresh.status -ne "completed") { throw "Refresh não foi concluído." }

$markets = Test-Endpoint "Markets" "GET" "/markets/"
$marketCount = @($markets).Count
if ($refresh.markets -ne $marketCount) {
    throw "Refresh retornou $($refresh.markets), mas o repository possui $marketCount."
}

$status = Test-Endpoint "Hyperliquid Status" "GET" "/connectors/hyperliquid"
if ($status.connected -ne $true) { throw "Status do HyperliquidConnector está offline." }
if ($status.error) { throw "Status do HyperliquidConnector contém erro: $($status.error)" }

$opportunities = Test-Endpoint "Opportunities" "GET" "/opportunities/"
$opportunityCount = @($opportunities).Count

Write-Host "`nResumo" -ForegroundColor Yellow
Write-Host "Mercados HIP-4 normalizados: $marketCount"
Write-Host "Oportunidades atuais: $opportunityCount"
Write-Host "Execução live: bloqueada"
Write-Host "`nTodos os testes HTTP da Fase 2 passaram." -ForegroundColor Green
