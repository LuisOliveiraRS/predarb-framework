# PredArb — Fase 8AE: Runtime do Histórico da Validação Final Paper

A Fase 8AE registra periodicamente as avaliações da Fase 8AC no histórico
persistente criado na Fase 8AD.

## Rotas

- `GET /paper/final-validation/history-runtime/health`
- `GET /paper/final-validation/history-runtime/status`
- `GET /paper/final-validation/history-runtime/last-cycle`
- `POST /paper/final-validation/history-runtime/cycle`
- `POST /paper/final-validation/history-runtime/start`
- `POST /paper/final-validation/history-runtime/stop`
- `POST /paper/final-validation/history-runtime/reset-statistics`

## Confirmações

```text
CAPTURE-FINAL-PAPER-VALIDATION
START-FINAL-PAPER-VALIDATION-HISTORY-RUNTIME
STOP-FINAL-PAPER-VALIDATION-HISTORY-RUNTIME
RESET-FINAL-PAPER-VALIDATION-HISTORY-RUNTIME
```

## Segurança

- início manual obrigatório;
- nenhum hook de inicialização automática;
- nenhuma autorização da próxima fase;
- nenhuma execução live ou financeira;
- nenhum envio de ordem;
- apenas avaliações finais são persistidas.

## Variáveis opcionais

```env
PAPER_FINAL_VALIDATION_HISTORY_RUNTIME_ENABLED=true
PAPER_FINAL_VALIDATION_HISTORY_RUNTIME_INTERVAL_SECONDS=300
```

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8ae_final_validation_history_runtime.py"
```

## Testes

```powershell
python -m pytest -q tests\test_final_paper_validation_history_runtime.py
python -m pytest -q
```

Com os 239 testes anteriores, a expectativa é de 247 testes aprovados.

## Validação HTTP

```powershell
python ".\scripts\real_tests\phase8ae_final_validation_history_runtime_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```
