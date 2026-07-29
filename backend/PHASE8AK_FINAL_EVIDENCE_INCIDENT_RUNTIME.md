# PredArb — Fase 8AK: Runtime dos Incidentes das Evidências Finais

A Fase 8AK adiciona um runtime manual para avaliar periodicamente o monitor
da Fase 8AH e atualizar o diário persistente criado na Fase 8AI.

## Rotas

- `GET /paper/final-validation/evidence/incident-runtime/health`
- `GET /paper/final-validation/evidence/incident-runtime/status`
- `GET /paper/final-validation/evidence/incident-runtime/last-cycle`
- `POST /paper/final-validation/evidence/incident-runtime/cycle`
- `POST /paper/final-validation/evidence/incident-runtime/start`
- `POST /paper/final-validation/evidence/incident-runtime/stop`
- `POST /paper/final-validation/evidence/incident-runtime/reset-statistics`

## Confirmações

```text
CAPTURE-FINAL-PAPER-EVIDENCE-INCIDENTS
START-FINAL-PAPER-EVIDENCE-INCIDENT-RUNTIME
STOP-FINAL-PAPER-EVIDENCE-INCIDENT-RUNTIME
RESET-FINAL-PAPER-EVIDENCE-INCIDENT-RUNTIME
```

## Recursos

- captura manual;
- atualização periódica do diário;
- início e parada explícitos;
- início duplicado idempotente;
- captura imediata opcional;
- contadores de incidentes criados, atualizados, reativados e resolvidos;
- contadores por estado do monitor;
- registro de falhas;
- reset somente com o runtime parado;
- intervalo entre 30 e 86400 segundos pela API.

## Segurança

- o runtime não inicia automaticamente;
- não modifica o arquivo probatório da Fase 8AG;
- não autoriza a próxima fase;
- não envia ordens;
- não habilita execução live ou financeira;
- somente o diário de incidentes é atualizado;
- todas as operações administrativas exigem confirmação.

## Variáveis opcionais

```env
PAPER_FINAL_EVIDENCE_INCIDENT_RUNTIME_ENABLED=true
PAPER_FINAL_EVIDENCE_INCIDENT_RUNTIME_INTERVAL_SECONDS=300
```

Não é necessário alterar o `.env`.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8ak_final_evidence_incident_runtime.py"
```

## Testes

```powershell
python -m pytest -q tests\test_final_paper_validation_evidence_incident_runtime.py
python -m pytest -q
```

Com os 285 testes anteriores, a expectativa é de 293 testes aprovados.

## Validação HTTP

```powershell
python ".\scripts\real_tests\phase8ak_final_evidence_incident_runtime_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```
