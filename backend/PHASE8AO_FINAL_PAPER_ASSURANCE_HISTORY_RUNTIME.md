# PredArb — Fase 8AO: Runtime do Histórico da Garantia Final Paper

A Fase 8AO adiciona um runtime manual para avaliar periodicamente a Garantia
Operacional Final Paper da Fase 8AM e persistir o resultado no histórico da
Fase 8AN.

## Rotas

- `GET /paper/final-assurance/history-runtime/health`
- `GET /paper/final-assurance/history-runtime/status`
- `GET /paper/final-assurance/history-runtime/last-cycle`
- `POST /paper/final-assurance/history-runtime/cycle`
- `POST /paper/final-assurance/history-runtime/start`
- `POST /paper/final-assurance/history-runtime/stop`
- `POST /paper/final-assurance/history-runtime/reset-statistics`

## Confirmações

```text
CAPTURE-FINAL-PAPER-ASSURANCE
START-FINAL-PAPER-ASSURANCE-HISTORY-RUNTIME
STOP-FINAL-PAPER-ASSURANCE-HISTORY-RUNTIME
RESET-FINAL-PAPER-ASSURANCE-HISTORY-RUNTIME
```

## Recursos

- captura manual da garantia;
- captura periódica do estado consolidado;
- início e parada explícitos;
- início duplicado idempotente;
- captura imediata opcional;
- contadores `ASSURED`, `WARNING`, `BLOCKED` e `NO_DATA`;
- registro de falhas;
- reset somente com o runtime parado;
- intervalo entre 30 e 86400 segundos pela API.

## Segurança

- o runtime não inicia automaticamente;
- não modifica os componentes avaliados;
- não altera o arquivo probatório;
- não autoriza a próxima fase;
- não envia ordens;
- não habilita execução live ou financeira;
- somente o histórico da garantia final é atualizado;
- todas as operações administrativas exigem confirmação.

## Variáveis opcionais

```env
PAPER_FINAL_ASSURANCE_HISTORY_RUNTIME_ENABLED=true
PAPER_FINAL_ASSURANCE_HISTORY_RUNTIME_INTERVAL_SECONDS=300
```

Não é necessário alterar o `.env`.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8ao_final_paper_assurance_history_runtime.py"
```

## Testes

```powershell
python -m pytest -q tests\test_final_paper_assurance_history_runtime.py
python -m pytest -q
```

A Fase 8AO adiciona 9 testes. Considerando os 315 testes anteriores, a
expectativa é de 324 testes aprovados.

## Validação HTTP

```powershell
python ".\scripts\real_tests\phase8ao_final_paper_assurance_history_runtime_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```
