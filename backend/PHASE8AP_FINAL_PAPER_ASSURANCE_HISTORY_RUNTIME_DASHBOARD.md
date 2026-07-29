# PredArb — Fase 8AP: Dashboard do Runtime do Histórico da Garantia Final

A Fase 8AP adiciona uma interface operacional para o runtime criado na
Fase 8AO.

## Novas rotas

- `GET /paper/final-assurance/history-runtime/dashboard`
- `GET /paper/final-assurance/history-runtime/snapshot`

## Recursos

- estado do runtime;
- status e score atuais da garantia final;
- ciclos, sucessos e falhas;
- contadores `ASSURED`, `WARNING`, `BLOCKED` e `NO_DATA`;
- quantidade de avaliações persistidas;
- maior sequência `ASSURED`;
- quantidade de transições;
- início com intervalo configurável;
- parada manual;
- captura imediata;
- reset das estatísticas;
- visualização do último ciclo.

## Segurança

- abrir o dashboard não inicia o runtime;
- o snapshot não captura nem persiste avaliações;
- todas as ações administrativas exigem confirmação;
- o intervalo mínimo pela API é de 30 segundos;
- somente o histórico da garantia final é atualizado;
- os componentes avaliados não são modificados;
- a próxima fase não é autorizada;
- execução live e financeira permanecem bloqueadas.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8ap_final_paper_assurance_history_runtime_dashboard.py"
```

## Testes

```powershell
python -m pytest -q tests\test_final_paper_assurance_history_runtime_dashboard.py
python -m pytest -q
```

A Fase 8AP adiciona 6 testes. Considerando os 324 testes anteriores, a
expectativa é de 330 testes aprovados.

## Validação HTTP

```powershell
python ".\scripts\real_tests\phase8ap_final_paper_assurance_history_runtime_dashboard_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Dashboard:

```text
http://127.0.0.1:8000/paper/final-assurance/history-runtime/dashboard
```
