# PredArb — Fase 8AF: Dashboard do Runtime da Validação Final Paper

A Fase 8AF adiciona uma interface operacional para controlar o runtime criado
na Fase 8AE.

## Novas rotas

- `GET /paper/final-validation/history-runtime/dashboard`
- `GET /paper/final-validation/history-runtime/snapshot`

## Recursos

- estado atual do runtime;
- status e score da validação final;
- total de ciclos, sucessos e falhas;
- quantidade de avaliações persistidas;
- maior sequência `PAPER_VALIDATED`;
- início com intervalo configurável;
- parada manual;
- captura imediata;
- reset das estatísticas;
- visualização do último ciclo.

## Segurança

- abrir o dashboard não inicia o runtime;
- o snapshot não registra avaliações;
- todas as ações administrativas exigem confirmação;
- o intervalo mínimo é de 30 segundos;
- somente avaliações finais são persistidas;
- a próxima fase permanece não autorizada;
- execução live e financeira permanecem bloqueadas.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8af_final_validation_history_runtime_dashboard.py"
```

## Testes

```powershell
python -m pytest -q tests\test_final_paper_validation_history_runtime_dashboard.py
python -m pytest -q
```

Com os 247 testes anteriores, a expectativa é de 253 testes aprovados.

## Validação HTTP

```powershell
python ".\scripts\real_tests\phase8af_final_validation_history_runtime_dashboard_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Dashboard:

```text
http://127.0.0.1:8000/paper/final-validation/history-runtime/dashboard
```
