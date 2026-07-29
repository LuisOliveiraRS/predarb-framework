# PredArb — Fase 8W: Runtime do Histórico do Centro de Garantia

A Fase 8W adiciona um runtime manual para registrar periodicamente snapshots do
Centro de Garantia da Fase 8U no histórico persistente criado na Fase 8V.

## Novas rotas

- `GET /paper/certification/assurance/history-runtime/health`
- `GET /paper/certification/assurance/history-runtime/status`
- `GET /paper/certification/assurance/history-runtime/last-cycle`
- `POST /paper/certification/assurance/history-runtime/cycle`
- `POST /paper/certification/assurance/history-runtime/start`
- `POST /paper/certification/assurance/history-runtime/stop`
- `POST /paper/certification/assurance/history-runtime/reset-statistics`

## Confirmações obrigatórias

```text
CAPTURE-PAPER-CERTIFICATION-ASSURANCE
START-PAPER-ASSURANCE-HISTORY-RUNTIME
STOP-PAPER-ASSURANCE-HISTORY-RUNTIME
RESET-PAPER-ASSURANCE-HISTORY-RUNTIME
```

## Recursos

- ciclo manual;
- captura periódica;
- início e parada explícitos;
- início duplicado idempotente;
- captura imediata opcional;
- contadores por status;
- registro de falhas sem autorizar execução;
- reset somente com o runtime parado;
- limite de intervalo entre 30 e 86400 segundos pela API.

## Segurança

- o runtime não inicia automaticamente;
- nenhuma ordem é enviada;
- nenhuma sessão Paper é iniciada;
- nenhuma autorização live é criada;
- apenas snapshots do Centro de Garantia são persistidos;
- todas as guardas financeiras permanecem falsas.

## Variáveis opcionais

```env
PAPER_ASSURANCE_HISTORY_RUNTIME_ENABLED=true
PAPER_ASSURANCE_HISTORY_RUNTIME_INTERVAL_SECONDS=300
```

Não é necessário alterar o `.env`.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8w_assurance_history_runtime.py"
```

## Testes

```powershell
python -m pytest -q tests\test_paper_certification_assurance_history_runtime.py
python -m pytest -q
```

Com os 179 testes anteriores, a expectativa é de 187 testes aprovados.

## Validação HTTP

Reinicie o servidor e execute:

```powershell
python ".\scripts\real_tests\phase8w_assurance_history_runtime_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```
