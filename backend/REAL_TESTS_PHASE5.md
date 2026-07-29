# PredArb — Fase 5: Conta Paper Persistente

Esta fase adiciona uma conta virtual persistente, totalmente separada do OMS e da execução live.

## Segurança

- nenhuma ordem é enviada a connectors;
- `ExecutionWorker` permanece desabilitado nos testes;
- `ExecutionEngine` continua bloqueado por padrão;
- a conta aceita somente relatórios `mode=PAPER` e `status=FILLED`;
- a persistência usa JSON com gravação atômica, sem pickle ou joblib;
- commits repetidos são bloqueados por `order_id`;
- falhas de saldo restauram o estado anterior.

## Componentes

- `PaperAccount`: carteira, posições, trades, equity e PnL;
- `PaperAccountRepository`: persistência JSON atômica;
- `PaperAccountRuntime`: load/save no lifecycle da aplicação;
- `PaperAccountStage`: persistência opcional após `PaperStage`;
- API `/paper/*` para consulta e operações exclusivamente simuladas.

O Pipeline paper padrão continua sem persistir estado. Para persistir explicitamente:

```python
pipeline = PipelineBuilder().build_paper(
    persist_paper_account=True,
    paper_account_persist=True,
)
```

## Configuração

```env
PAPER_ACCOUNT_ENABLED=true
PAPER_ACCOUNT_AUTO_LOAD=true
PAPER_ACCOUNT_AUTO_SAVE=true
PAPER_ACCOUNT_PATH=paper_data/paper_account.json
PAPER_INITIAL_BALANCE=10000
```

## Testes

```powershell
python -m pytest -q
python ".\scripts\real_tests\phase5_persistent_paper_account.py"
```

Resultado esperado:

```text
18 passed
Aprovados: 10
Falhas:    0
```

## Servidor

Terminal 1:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
& "C:\predarb-framework\backend\scripts\real_tests\phase5_start_server.ps1"
```

Terminal 2:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
cd C:\predarb-framework\backend
& ".\scripts\real_tests\phase5_server_smoke.ps1"
```

Resultado esperado:

```text
Todos os testes HTTP da Fase 5 passaram.
```

## Endpoints

```text
GET  /paper/status
GET  /paper/account
GET  /paper/positions
GET  /paper/trades
POST /paper/commit
POST /paper/mark
POST /paper/settle/{position_id}
POST /paper/save
POST /paper/reset?confirm=RESET-PAPER
```

O reset exige a confirmação literal `RESET-PAPER`.
