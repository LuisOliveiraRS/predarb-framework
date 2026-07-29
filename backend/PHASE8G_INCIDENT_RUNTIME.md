# PredArb — Fase 8G: runtime controlado de incidentes

A Fase 8G automatiza a captura do monitor no journal da Fase 8E, mas mantém
início e encerramento manuais, com confirmação explícita.

## Novas rotas

- `GET /paper/performance/incidents/runtime/health`
- `GET /paper/performance/incidents/runtime/status`
- `GET /paper/performance/incidents/runtime/last-cycle`
- `POST /paper/performance/incidents/runtime/cycle`
- `POST /paper/performance/incidents/runtime/start`
- `POST /paper/performance/incidents/runtime/stop`
- `POST /paper/performance/incidents/runtime/reset-statistics`

## Confirmações

```text
CAPTURE-PAPER-INCIDENTS
START-PAPER-INCIDENT-RUNTIME
STOP-PAPER-INCIDENT-RUNTIME
RESET-PAPER-INCIDENT-RUNTIME
```

## Segurança

- não inicia automaticamente;
- não executa trades;
- não chama endpoints de compra ou venda;
- captura apenas snapshots de monitoramento;
- persiste somente no journal de incidentes;
- execução live e financeira permanecem `false`.

## Variáveis opcionais

```env
PAPER_INCIDENT_RUNTIME_ENABLED=true
PAPER_INCIDENT_RUNTIME_INTERVAL_SECONDS=60
```

Não é necessário alterar o `.env`.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8g_incident_runtime.py"
```

## Testes

```powershell
python -m pytest -q tests\test_paper_performance_incident_runtime.py
python -m pytest -q
```

Com os 60 testes anteriores, a expectativa é de 68 testes aprovados.

## Validação HTTP

Reinicie o servidor da Fase 8 e execute:

```powershell
python ".\scripts\real_tests\phase8g_incident_runtime_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```
