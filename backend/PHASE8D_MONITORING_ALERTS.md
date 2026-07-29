# PredArb — Fase 8D: monitoramento e alertas do Paper Trading

A Fase 8D adiciona uma camada de diagnóstico somente leitura sobre os dados
consolidados nas fases 8B e 8C.

## Novas rotas

- `GET /paper/performance/monitor/health`
- `GET /paper/performance/monitor/alerts`
- `GET /paper/performance/monitor/score`
- `GET /paper/performance/monitor/snapshot`
- `GET /paper/performance/monitor/dashboard`

## Regras monitoradas

- violações de segurança;
- erros de endpoint;
- taxa de falha dos ciclos;
- taxa mínima de sucesso;
- drawdown máximo;
- dados desatualizados;
- ausência de relatórios, ciclos ou trades.

## Variáveis opcionais

```env
PAPER_MONITOR_MAX_FAILED_CYCLE_RATE=0.20
PAPER_MONITOR_MIN_SUCCESS_CYCLE_RATE=0.60
PAPER_MONITOR_MAX_DRAWDOWN_RATE=0.05
PAPER_MONITOR_STALE_HOURS=24
```

Não é necessário alterar o `.env`; esses são apenas os padrões.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8d_monitor.py"
```

## Testes

```powershell
python -m pytest -q tests\test_paper_performance_monitor.py
python -m pytest -q
```

Com os 39 testes anteriores, a expectativa é de 46 testes aprovados.

## Validação HTTP

Reinicie o servidor da Fase 8 e execute:

```powershell
python ".\scripts\real_tests\phase8d_monitor_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Dashboard:

```text
http://127.0.0.1:8000/paper/performance/monitor/dashboard
```
