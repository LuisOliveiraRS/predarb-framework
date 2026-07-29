# PredArb — Fase 6: Dashboard Paper e curva de equity

Esta fase integra a conta Paper persistente ao Dashboard e adiciona um histórico limitado da curva de equity. Nenhum componente da Fase 6 habilita execução live.

## Componentes

- `PaperEquityTracker`: histórico thread-safe e limitado da equity.
- migração transparente dos estados Paper versão 1.
- persistência da curva no JSON da conta.
- analytics: pico, mínimo, retorno e drawdown máximo.
- Dashboard: saldo, equity, PnL, posições, trades e gráfico SVG sem biblioteca externa.
- endpoints `GET /paper/equity` e `GET /paper/statistics`.
- teste de sessão prolongada e sonda HTTP.

## Testes locais

```powershell
python -m pytest -q
python ".\scripts\real_tests\phase6_paper_dashboard_session.py"
```

Resultados esperados:

```text
22 passed
Aprovados: 8
Falhas:    0
```

## Servidor controlado

Terminal 1:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
& ".\scripts\real_tests\phase6_start_server.ps1"
```

Terminal 2:

```powershell
python ".\scripts\real_tests\phase6_server_session.py" `
    --base-url "http://127.0.0.1:8000" `
    --cycles 12 `
    --interval-seconds 0.25
```

Abra o Dashboard:

```text
http://127.0.0.1:8000/dashboard
```

Endpoints:

```text
GET /paper/account
GET /paper/equity
GET /paper/statistics
GET /dashboard/api/snapshot
```

## Proteções obrigatórias

```text
EXECUTION_WORKER_ENABLED=false
AI_EXECUTION_AUTHORIZED=false
AI_AUTO_LOAD_MODEL=false
paper.execution_authorized=false
paper.live_execution=false
```
