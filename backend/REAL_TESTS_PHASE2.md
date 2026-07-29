# PredArb — Testes reais da aplicação: Fase 2

Esta fase valida o conector público da Hyperliquid em modo estritamente somente leitura.

São testados:

- `POST /info` com `allMids`;
- `POST /info` com `outcomeMeta`;
- schema de outcomes HIP-4;
- codificação `#<10 * outcome + side>`;
- `HyperliquidProvider`;
- `HyperliquidParser`;
- `HyperliquidConnector`;
- startup da aplicação com apenas a Hyperliquid;
- refresh e persistência no `MarketRepository`;
- endpoints HTTP;
- bloqueio da execução live.

Não são utilizados:

- carteira;
- chave privada;
- API key;
- endpoint de ordens;
- `ExecutionWorker`;
- Scheduler;
- execução live.

## Teste automatizado

Na raiz do backend:

```powershell
python ".\scripts\real_tests\phase2_hyperliquid_readonly.py"
```

Relatório:

```text
real_test_reports\phase2_hyperliquid_readonly_report.json
```

A quantidade de mercados HIP-4 pode ser zero quando não houver outcomes ativos com preços válidos para os dois lados. Isso não é considerado falha de conectividade.

## Servidor Uvicorn

Terminal 1:

```powershell
$env:MOCK_CONNECTOR_ENABLED = "false"
$env:HYPERLIQUID_CONNECTOR_ENABLED = "true"
$env:INITIAL_MARKET_SYNC_ENABLED = "false"

$env:SCHEDULER_ENABLED = "false"
$env:EXECUTION_WORKER_ENABLED = "false"
$env:ROUTER_DASHBOARD_ENABLED = "false"

$env:AI_ADVISORY_ONLY = "true"
$env:AI_EXECUTION_AUTHORIZED = "false"
$env:AI_AUTO_LOAD_MODEL = "false"

$env:DATABASE_URL = "sqlite:///predarb_real_test_phase2.db"
$env:HYPERLIQUID_API_URL = "https://api.hyperliquid.xyz"
$env:HYPERLIQUID_TIMEOUT_SECONDS = "15"
$env:HYPERLIQUID_MAX_RETRIES = "1"
$env:HYPERLIQUID_RETRY_DELAY_SECONDS = "0.5"

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level info
```

Terminal 2:

```powershell
.\scripts\real_tests\phase2_server_smoke.ps1
```

Não habilite o Scheduler, o Execution Worker ou qualquer executor real nesta fase.
