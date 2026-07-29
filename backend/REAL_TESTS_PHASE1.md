# PredArb — Testes reais da aplicação: Fase 1

Esta fase executa o backend completo em ambiente controlado:

- banco SQLite local de teste;
- `MockConnector` real;
- sincronização inicial real do repositório;
- Arbitrage Engine;
- Pipeline `analysis`;
- AI consultiva;
- Pipeline `paper`;
- Dashboard;
- proteção da execução `live`.

A Hyperliquid, o Scheduler, o Execution Worker e o Router Dashboard permanecem desligados.

## Execução automatizada

Na raiz do backend:

```powershell
python ".\scripts\real_tests\phase1_integration_test.py"
```

Resultado esperado:

```text
Aprovados: 11
Falhas:    0
```

O relatório será gravado em:

```text
real_test_reports\phase1_integration_report.json
```

## Teste com servidor Uvicorn

Terminal 1:

```powershell
$env:MOCK_CONNECTOR_ENABLED = "true"
$env:HYPERLIQUID_CONNECTOR_ENABLED = "false"
$env:INITIAL_MARKET_SYNC_ENABLED = "true"
$env:SCHEDULER_ENABLED = "false"
$env:EXECUTION_WORKER_ENABLED = "false"
$env:ROUTER_DASHBOARD_ENABLED = "false"
$env:AI_ADVISORY_ONLY = "true"
$env:AI_EXECUTION_AUTHORIZED = "false"
$env:AI_AUTO_LOAD_MODEL = "false"
$env:DATABASE_URL = "sqlite:///predarb_real_test.db"

uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level info
```

Terminal 2:

```powershell
.\scripts\real_tests\phase1_server_smoke.ps1
```

Não habilite a Hyperliquid nem a execução live nesta fase.
