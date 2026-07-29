# PredArb — Fase 8A: sessão Paper prolongada e relatório consolidado

Esta etapa executa uma sessão Paper real por HTTP, coleta histórico operacional e
gera métricas sem alterar o código da aplicação.

## Segurança preservada

- `EXECUTION_WORKER_ENABLED=false`
- `AI_EXECUTION_AUTHORIZED=false`
- `PAPER_SESSION_AUTO_START=false`
- início explícito por `START-PAPER-SESSION`
- conta e relatório exclusivos da Fase 8
- nenhum endpoint de execução live é utilizado

## Arquivos gerados

Em `real_test_reports`:

- `phase8_long_session_*.json`: relatório consolidado;
- `phase8_long_session_*.csv`: série temporal resumida;
- `phase8_long_session_*.jsonl`: snapshots completos de cada coleta.

## Execução

### Terminal 1

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
& ".\scripts\real_tests\phase8_start_server.ps1"
```

### Terminal 2 — smoke test de 2 minutos

```powershell
python ".\scripts\real_tests\phase8_long_paper_session.py" `
    --base-url "http://127.0.0.1:8000" `
    --duration-minutes 2 `
    --poll-seconds 10 `
    --reset `
    --confirm-reset "RESET-PHASE8-DATA" `
    --label "smoke"
```

### Sessão de 30 minutos

Não use `--reset` para continuar com o estado persistido criado no smoke test.

```powershell
python ".\scripts\real_tests\phase8_long_paper_session.py" `
    --base-url "http://127.0.0.1:8000" `
    --duration-minutes 30 `
    --poll-seconds 15 `
    --label "30min"
```

### Resumo do relatório mais recente

```powershell
python ".\scripts\real_tests\phase8_report_summary.py"
```

## Critérios de aprovação

- pelo menos uma amostra coletada;
- aumento do número de ciclos;
- zero erro de endpoint;
- zero flag de execução live;
- zero autorização de IA para executar ordens.

`NO_SIGNAL` não é falha. Ele é esperado quando não existe arbitragem real no
momento da coleta.
