# PredArb — Fase 8S: Runtime dos Incidentes das Evidências

A Fase 8S adiciona um runtime manual e controlado para capturar periodicamente
o monitor da Fase 8P no journal da Fase 8Q.

## Novas rotas

- `GET /paper/certification/evidence/incident-runtime/health`
- `GET /paper/certification/evidence/incident-runtime/status`
- `GET /paper/certification/evidence/incident-runtime/last-cycle`
- `POST /paper/certification/evidence/incident-runtime/cycle`
- `POST /paper/certification/evidence/incident-runtime/start`
- `POST /paper/certification/evidence/incident-runtime/stop`
- `POST /paper/certification/evidence/incident-runtime/reset-statistics`

## Confirmações obrigatórias

```text
CAPTURE-PAPER-EVIDENCE-INCIDENTS
START-PAPER-EVIDENCE-INCIDENT-RUNTIME
STOP-PAPER-EVIDENCE-INCIDENT-RUNTIME
RESET-PAPER-EVIDENCE-INCIDENT-RUNTIME
```

## Segurança

- o runtime não inicia automaticamente;
- início manual obrigatório;
- intervalo mínimo de 30 segundos pela API;
- nenhuma evidência é criada;
- nenhuma certificação é capturada;
- apenas o snapshot do monitor é registrado no journal;
- nenhuma ordem ou sessão Paper é iniciada;
- execução live e financeira permanecem bloqueadas.

## Variáveis opcionais

```env
PAPER_EVIDENCE_INCIDENT_RUNTIME_ENABLED=true
PAPER_EVIDENCE_INCIDENT_RUNTIME_INTERVAL_SECONDS=300
```

Não é necessário alterar o `.env`.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8s_evidence_incident_runtime.py"
```

## Testes

```powershell
python -m pytest -q tests\test_paper_certification_evidence_incident_runtime.py
python -m pytest -q
```

Com os 151 testes anteriores, a expectativa é de 159 testes aprovados.

## Validação HTTP

Reinicie o servidor e execute:

```powershell
python ".\scripts\real_tests\phase8s_evidence_incident_runtime_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```
