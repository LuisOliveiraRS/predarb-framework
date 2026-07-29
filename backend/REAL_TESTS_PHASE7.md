# PredArb — Fase 7: Sessão Paper automatizada com limites de risco

Esta fase adiciona uma sessão Paper explicitamente iniciada, sem execução financeira real.

## Proteções permanentes

- `EXECUTION_WORKER_ENABLED=false`
- `AI_EXECUTION_AUTHORIZED=false`
- `PAPER_SESSION_AUTO_START=false`
- início exige `START-PAPER-SESSION`
- todas as ordens são processadas por `PaperStage`
- a conta e o relatório usam JSON atômico

## Limites avaliados antes de OrderStage

- stake máxima por oportunidade;
- exposição total;
- exposição por mercado;
- posições abertas;
- trades diários;
- perda diária;
- drawdown máximo;
- ROI mínimo;
- confiança mínima;
- score de risco máximo;
- caixa disponível.

## Teste integrado

```powershell
python ".\scripts\real_tests\phase7_risk_managed_session.py"
```

Resultado esperado:

```text
Aprovados: 7
Falhas:    0
```

## Servidor controlado

Terminal 1:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
& ".\scripts\real_tests\phase7_start_server.ps1"
```

Terminal 2:

```powershell
python ".\scripts\real_tests\phase7_server_session.py" `
    --base-url "http://127.0.0.1:8000" `
    --wait-seconds 25
```

## Endpoints

```text
GET  /paper/risk/status
GET  /paper/session/status
GET  /paper/session/report
POST /paper/session/cycle
POST /paper/session/start?confirm=START-PAPER-SESSION
POST /paper/session/stop
POST /paper/session/reset-report?confirm=RESET-PAPER-SESSION-REPORT
```

A execução da sessão pode produzir `NO_SIGNAL` quando os conectores reais não oferecem uma oportunidade cross-platform no momento. Esse resultado não é falha. O teste HTTP inclui uma oportunidade controlada apenas para validar os limites e o isolamento operacional.
