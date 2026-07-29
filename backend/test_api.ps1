$urls = @(
    "http://127.0.0.1:8000/health",
    "http://127.0.0.1:8000/markets",
    "http://127.0.0.1:8000/arbitrage",
    "http://127.0.0.1:8000/opportunities",
    "http://127.0.0.1:8000/connectors",
    "http://127.0.0.1:8000/plugins"
)

foreach ($url in $urls) {
    Write-Host ""
    Write-Host "========================================"
    Write-Host "TESTANDO: $url"
    Write-Host "========================================"

    try {
        Invoke-RestMethod $url
    }
    catch {
        Write-Host $_
    }
}