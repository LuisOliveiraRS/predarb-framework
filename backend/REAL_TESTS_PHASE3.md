# PredArb — Testes Reais, Fase 3

## Objetivo

Validar a aplicação com:

- `MockConnector` habilitado;
- `HyperliquidConnector` habilitado em modo somente leitura;
- sincronização inicial habilitada;
- `BackgroundScheduler` habilitado;
- um único job `market_update_task`;
- atualização recorrente do `MarketRepository`;
- ausência de duplicação ou acúmulo de mercados;
- comparação cross-platform e Pipeline de análise;
- Dashboard consistente;
- AI exclusivamente consultiva;
- execução live bloqueada.

## Segurança

A fase mantém permanentemente:

```env
EXECUTION_WORKER_ENABLED=false
AI_ADVISORY_ONLY=true
AI_EXECUTION_AUTHORIZED=false
AI_AUTO_LOAD_MODEL=false
```

Nenhuma carteira, chave privada, API key ou endpoint de envio de ordens é utilizado.

## Arquivos

```text
scripts/real_tests/phase3_scheduler_stability.py
scripts/real_tests/phase3_server_smoke.ps1
scripts/real_tests/phase3_soak_monitor.ps1
REAL_TESTS_PHASE3.md
```

## 1. Teste integrado no próprio processo

Na raiz do backend:

```powershell
cd C:\predarb-framework\backend
python ".\scripts\real_tests\phase3_scheduler_stability.py"
```

O teste usa, por padrão:

```text
intervalo do scheduler: 5 segundos
observação:             18 segundos
```

É possível ajustar apenas para o processo atual:

```powershell
$env:PREDARB_PHASE3_INTERVAL_SECONDS = "5"
$env:PREDARB_PHASE3_OBSERVATION_SECONDS = "20"
python ".\scripts\real_tests\phase3_scheduler_stability.py"
```

Relatório:

```text
real_test_reports\phase3_scheduler_stability_report.json
```

## 2. Servidor Uvicorn

No Terminal 1:

```powershell
cd C:\predarb-framework\backend

$env:MOCK_CONNECTOR_ENABLED = "true"
$env:HYPERLIQUID_CONNECTOR_ENABLED = "true"
$env:INITIAL_MARKET_SYNC_ENABLED = "true"

$env:SCHEDULER_ENABLED = "true"
$env:MARKET_UPDATE_INTERVAL_SECONDS = "5"
$env:EXECUTION_WORKER_ENABLED = "false"
$env:ROUTER_DASHBOARD_ENABLED = "false"

$env:AI_ENABLED = "true"
$env:AI_PIPELINE_ENABLED = "true"
$env:AI_STRICT_FEATURES = "false"
$env:AI_FAIL_ON_ERROR = "false"
$env:AI_ADVISORY_ONLY = "true"
$env:AI_EXECUTION_AUTHORIZED = "false"
$env:AI_AUTO_LOAD_MODEL = "false"

$env:DATABASE_URL = "sqlite:///predarb_real_test_phase3.db"

$env:HYPERLIQUID_API_URL = "https://api.hyperliquid.xyz"
$env:HYPERLIQUID_TIMEOUT_SECONDS = "15"
$env:HYPERLIQUID_MAX_RETRIES = "1"
$env:HYPERLIQUID_RETRY_DELAY_SECONDS = "0.5"

python -m uvicorn app.main:app `
    --host 127.0.0.1 `
    --port 8000 `
    --log-level info
```

## 3. Smoke test HTTP

No Terminal 2:

```powershell
cd C:\predarb-framework\backend
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

& ".\scripts\real_tests\phase3_server_smoke.ps1"
```

Parâmetros opcionais:

```powershell
& ".\scripts\real_tests\phase3_server_smoke.ps1" `
    -BaseUrl "http://127.0.0.1:8000" `
    -ObservationSeconds 20 `
    -PollSeconds 2
```

Relatório:

```text
real_test_reports\phase3_server_smoke_report.json
```

## 4. Soak test opcional

Com o servidor ainda ativo:

```powershell
& ".\scripts\real_tests\phase3_soak_monitor.ps1" `
    -DurationSeconds 120 `
    -PollSeconds 5
```

Para uma observação de dez minutos:

```powershell
& ".\scripts\real_tests\phase3_soak_monitor.ps1" `
    -DurationSeconds 600 `
    -PollSeconds 5
```

O monitor falha se detectar:

- aplicação não saudável;
- scheduler parado;
- quantidade de jobs diferente de um;
- execução operacional habilitada;
- duplicação de mercados;
- alteração dos cinco mercados mock;
- ausência de avanço no `repository.updated_at`;
- três erros consecutivos de connector, por padrão.

Relatório:

```text
real_test_reports\phase3_soak_report.json
```

## Resultado necessário para avançar

```text
Teste integrado: 0 falhas
Smoke HTTP: todos os testes passaram
Soak: PASS
Scheduler: running=true, jobs=1
Connectors: mock + hyperliquid
Execution Worker: false
AI execution_authorized: false
Mercados duplicados: 0
```

A existência de uma oportunidade com uma perna Hyperliquid não é obrigatória. Ela depende de haver, no momento do teste, perguntas reais compatíveis com os mercados simulados. A ausência dessa rota gera apenas aviso.
