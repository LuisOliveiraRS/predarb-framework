# PredArb — Fase 8AB: Dashboard do Runtime do Histórico do Gate

A Fase 8AB adiciona uma interface operacional para controlar o runtime criado
na Fase 8AA.

## Novas rotas

- `GET /paper/certification/assurance/gate/history-runtime/dashboard`
- `GET /paper/certification/assurance/gate/history-runtime/snapshot`

## Recursos

- estado atual do runtime;
- status e score atuais do gate;
- total de ciclos, sucessos e falhas;
- quantidade de avaliações persistidas;
- maior sequência `QUALIFIED`;
- início com intervalo configurável;
- parada manual;
- captura imediata;
- reset das estatísticas;
- visualização do último ciclo.

## Segurança

- o snapshot não inicia o runtime;
- abrir o dashboard não registra avaliações;
- todas as ações exigem confirmação;
- o intervalo mínimo é de 30 segundos;
- somente relatórios do gate são persistidos;
- execução live e financeira continuam bloqueadas.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8ab_assurance_gate_history_runtime_dashboard.py"
```

## Testes

```powershell
python -m pytest -q tests\test_paper_certification_assurance_gate_history_runtime_dashboard.py
python -m pytest -q
```

Com os 217 testes anteriores, a expectativa é de 223 testes aprovados.

## Validação HTTP

Reinicie o servidor e execute:

```powershell
python ".\scripts\real_tests\phase8ab_assurance_gate_history_runtime_dashboard_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Dashboard:

```text
http://127.0.0.1:8000/paper/certification/assurance/gate/history-runtime/dashboard
```
