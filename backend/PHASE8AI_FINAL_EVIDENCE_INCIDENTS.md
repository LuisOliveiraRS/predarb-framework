# PredArb — Fase 8AI: Diário de Incidentes das Evidências Finais

A Fase 8AI transforma os alertas produzidos pelo monitor da Fase 8AH em um
diário persistente de incidentes operacionais.

## Recursos

- identificadores determinísticos;
- abertura e atualização de incidentes;
- resolução automática quando o alerta desaparece;
- reativação quando o alerta retorna;
- reconhecimento administrativo;
- snapshots compactos do monitor;
- persistência JSON com gravação atômica;
- proteção por `RLock`;
- validação fail-closed das guardas.

## Estados

```text
ACTIVE
RESOLVED
```

## Rotas

- `GET /paper/final-validation/evidence/incidents/health`
- `GET /paper/final-validation/evidence/incidents/summary`
- `GET /paper/final-validation/evidence/incidents/active`
- `GET /paper/final-validation/evidence/incidents/history`
- `GET /paper/final-validation/evidence/incidents/snapshots`
- `GET /paper/final-validation/evidence/incidents/{incident_id}`
- `POST /paper/final-validation/evidence/incidents/capture`
- `POST /paper/final-validation/evidence/incidents/{incident_id}/acknowledge`

## Confirmações obrigatórias

```text
CAPTURE-FINAL-PAPER-EVIDENCE-INCIDENTS
ACK-FINAL-PAPER-EVIDENCE-INCIDENT
```

## Persistência

```text
paper_data/final_paper_validation_evidence_incidents.json
```

Variável opcional:

```env
PAPER_FINAL_EVIDENCE_INCIDENTS_PATH=paper_data/final_paper_validation_evidence_incidents.json
```

## Segurança

- nenhuma captura automática;
- nenhuma alteração no arquivo probatório da Fase 8AG;
- nenhuma autorização da próxima fase;
- nenhuma execução live ou financeira;
- nenhuma ordem;
- reconhecimento não resolve nem reabre incidentes.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8ai_final_evidence_incidents.py"
```

## Testes

```powershell
python -m pytest -q tests\test_final_paper_validation_evidence_incidents.py
python -m pytest -q
```

Com os 270 testes anteriores, a expectativa é de 279 testes aprovados.

## Validação HTTP

```powershell
python ".\scripts\real_tests\phase8ai_final_evidence_incidents_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```
