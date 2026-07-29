# PredArb — Fase 8AA: Runtime do Histórico do Gate de Qualificação

A Fase 8AA adiciona um runtime manual para registrar periodicamente as
avaliações do Gate da Fase 8Y no histórico persistente da Fase 8Z.

## Novas rotas

- `GET /paper/certification/assurance/gate/history-runtime/health`
- `GET /paper/certification/assurance/gate/history-runtime/status`
- `GET /paper/certification/assurance/gate/history-runtime/last-cycle`
- `POST /paper/certification/assurance/gate/history-runtime/cycle`
- `POST /paper/certification/assurance/gate/history-runtime/start`
- `POST /paper/certification/assurance/gate/history-runtime/stop`
- `POST /paper/certification/assurance/gate/history-runtime/reset-statistics`

## Confirmações obrigatórias

```text
CAPTURE-PAPER-ASSURANCE-QUALIFICATION
START-PAPER-ASSURANCE-GATE-HISTORY-RUNTIME
STOP-PAPER-ASSURANCE-GATE-HISTORY-RUNTIME
RESET-PAPER-ASSURANCE-GATE-HISTORY-RUNTIME
```

## Recursos

- ciclo manual;
- captura periódica;
- início e parada explícitos;
- início duplicado idempotente;
- captura imediata opcional;
- contadores por status do gate;
- registro de falhas;
- reset somente com o runtime parado;
- intervalo entre 30 e 86400 segundos pela API.

## Segurança

- o runtime não inicia automaticamente;
- não envia ordens;
- não inicia sessão Paper;
- não altera autorização da IA;
- não habilita execução live;
- apenas relatórios do gate são persistidos;
- todas as guardas financeiras permanecem falsas.

## Variáveis opcionais

```env
PAPER_ASSURANCE_GATE_HISTORY_RUNTIME_ENABLED=true
PAPER_ASSURANCE_GATE_HISTORY_RUNTIME_INTERVAL_SECONDS=300
```

Não é necessário alterar o `.env`.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8aa_assurance_gate_history_runtime.py"
```

## Testes

```powershell
python -m pytest -q tests\test_paper_certification_assurance_gate_history_runtime.py
python -m pytest -q
```

Com os 209 testes anteriores, a expectativa é de 217 testes aprovados.

## Validação HTTP

Reinicie o servidor e execute:

```powershell
python ".\scripts\real_tests\phase8aa_assurance_gate_history_runtime_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```
