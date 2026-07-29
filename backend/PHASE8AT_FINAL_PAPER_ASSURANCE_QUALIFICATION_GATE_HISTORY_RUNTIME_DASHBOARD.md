# PredArb — Fase 8AT: Dashboard do Runtime do Histórico do Gate

A Fase 8AT adiciona uma interface operacional para o runtime criado na
Fase 8AS.

## Novas rotas

- `GET /paper/final-assurance/qualification-gate/history-runtime/dashboard`
- `GET /paper/final-assurance/qualification-gate/history-runtime/snapshot`

## Recursos

- estado do runtime;
- status e score atuais do gate;
- ciclos, sucessos e falhas;
- contadores `QUALIFIED`, `PENDING`, `BLOCKED` e `NO_DATA`;
- quantidade de registros persistidos;
- último gate persistido;
- maior sequência `QUALIFIED`;
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
- somente o histórico do gate é atualizado;
- o gate e as evidências não são modificados;
- o estado `QUALIFIED` não autoriza execução real;
- a próxima fase não é autorizada;
- execução live e financeira permanecem bloqueadas.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8at_final_paper_assurance_qualification_gate_history_runtime_dashboard.py"
```

## Testes

```powershell
python -m pytest -q tests\test_final_paper_assurance_qualification_gate_history_runtime_dashboard.py
python -m pytest -q
```

A Fase 8AT adiciona 6 testes. Considerando os 355 testes anteriores, a
expectativa é de 361 testes aprovados.

## Validação HTTP

```powershell
python ".\scripts\real_tests\phase8at_final_paper_assurance_qualification_gate_history_runtime_dashboard_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Dashboard:

```text
http://127.0.0.1:8000/paper/final-assurance/qualification-gate/history-runtime/dashboard
```
