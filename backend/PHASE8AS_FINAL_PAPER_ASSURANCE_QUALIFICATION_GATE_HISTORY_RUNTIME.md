# PredArb — Fase 8AS: Runtime do Histórico do Gate de Qualificação

A Fase 8AS adiciona um runtime manual para avaliar periodicamente o Gate de
Qualificação da Garantia Final Paper da Fase 8AQ e persistir cada resultado
no histórico da Fase 8AR.

## Rotas

- `GET /paper/final-assurance/qualification-gate/history-runtime/health`
- `GET /paper/final-assurance/qualification-gate/history-runtime/status`
- `GET /paper/final-assurance/qualification-gate/history-runtime/last-cycle`
- `POST /paper/final-assurance/qualification-gate/history-runtime/cycle`
- `POST /paper/final-assurance/qualification-gate/history-runtime/start`
- `POST /paper/final-assurance/qualification-gate/history-runtime/stop`
- `POST /paper/final-assurance/qualification-gate/history-runtime/reset-statistics`

## Confirmações

```text
CAPTURE-FINAL-PAPER-ASSURANCE-QUALIFICATION-GATE
START-FINAL-PAPER-ASSURANCE-QUALIFICATION-GATE-HISTORY-RUNTIME
STOP-FINAL-PAPER-ASSURANCE-QUALIFICATION-GATE-HISTORY-RUNTIME
RESET-FINAL-PAPER-ASSURANCE-QUALIFICATION-GATE-HISTORY-RUNTIME
```

## Recursos

- captura manual do gate;
- captura periódica do estado de qualificação;
- início e parada explícitos;
- início duplicado idempotente;
- captura imediata opcional;
- contadores `QUALIFIED`, `PENDING`, `BLOCKED` e `NO_DATA`;
- registro de falhas;
- reset somente com o runtime parado;
- intervalo entre 30 e 86400 segundos pela API.

## Segurança

- o runtime não inicia automaticamente;
- não modifica o gate avaliado;
- não altera as evidências;
- não autoriza a próxima fase;
- não envia ordens;
- não habilita execução live ou financeira;
- somente o histórico do gate é atualizado;
- todas as operações administrativas exigem confirmação.

## Variáveis opcionais

```env
PAPER_FINAL_ASSURANCE_GATE_HISTORY_RUNTIME_ENABLED=true
PAPER_FINAL_ASSURANCE_GATE_HISTORY_RUNTIME_INTERVAL_SECONDS=300
```

Não é necessário alterar o `.env`.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8as_final_paper_assurance_qualification_gate_history_runtime.py"
```

## Testes

```powershell
python -m pytest -q tests\test_final_paper_assurance_qualification_gate_history_runtime.py
python -m pytest -q
```

A Fase 8AS adiciona 9 testes. Considerando os 346 testes anteriores, a
expectativa é de 355 testes aprovados.

## Validação HTTP

```powershell
python ".\scripts\real_tests\phase8as_final_paper_assurance_qualification_gate_history_runtime_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```
