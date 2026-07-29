# PredArb — Fase 8X: Dashboard do Runtime do Histórico da Garantia

A Fase 8X adiciona uma interface operacional para controlar o runtime criado
na Fase 8W.

## Novas rotas

- `GET /paper/certification/assurance/history-runtime/dashboard`
- `GET /paper/certification/assurance/history-runtime/snapshot`

## Recursos

- estado atual do runtime;
- status e score do Centro de Garantia;
- total de ciclos, sucessos e falhas;
- quantidade de snapshots persistidos;
- maior sequência `ASSURED`;
- início com intervalo configurável;
- parada manual;
- captura imediata;
- reset das estatísticas;
- visualização do último ciclo.

## Segurança

- o snapshot não inicia o runtime;
- o dashboard não captura implicitamente;
- todas as ações exigem confirmação;
- o intervalo mínimo é de 30 segundos;
- somente snapshots do Centro de Garantia são persistidos;
- execução live e financeira continuam bloqueadas.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8x_assurance_history_runtime_dashboard.py"
```

## Testes

```powershell
python -m pytest -q tests\test_paper_certification_assurance_history_runtime_dashboard.py
python -m pytest -q
```

Com os 187 testes anteriores, a expectativa é de 193 testes aprovados.

## Validação HTTP

Reinicie o servidor e execute:

```powershell
python ".\scripts\real_tests\phase8x_assurance_history_runtime_dashboard_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Dashboard:

```text
http://127.0.0.1:8000/paper/certification/assurance/history-runtime/dashboard
```
