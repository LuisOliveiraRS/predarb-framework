# PredArb — Fase 8Q: Journal de Incidentes das Evidências

A Fase 8Q registra e acompanha os alertas produzidos pelo monitor de
integridade da Fase 8P.

## Recursos

- criação determinística de incidentes;
- estados `ACTIVE` e `RESOLVED`;
- resolução automática quando o alerta desaparece;
- reativação quando o alerta retorna;
- contagem de ocorrências;
- reconhecimento administrativo;
- histórico de snapshots do monitor;
- persistência JSON com gravação atômica;
- nenhuma alteração no arquivo de evidências;
- nenhuma autorização financeira ou live.

## Novas rotas

- `GET /paper/certification/evidence/incidents/health`
- `GET /paper/certification/evidence/incidents/summary`
- `GET /paper/certification/evidence/incidents/active`
- `GET /paper/certification/evidence/incidents/history`
- `GET /paper/certification/evidence/incidents/snapshots`
- `GET /paper/certification/evidence/incidents/{incident_id}`
- `POST /paper/certification/evidence/incidents/capture`
- `POST /paper/certification/evidence/incidents/{incident_id}/acknowledge`

## Confirmações obrigatórias

```text
CAPTURE-PAPER-EVIDENCE-INCIDENTS
ACK-PAPER-EVIDENCE-INCIDENT
```

## Arquivo persistente

```text
paper_data/paper_certification_evidence_incidents.json
```

Variável opcional:

```env
PAPER_EVIDENCE_INCIDENTS_PATH=paper_data/paper_certification_evidence_incidents.json
```

Não é necessário alterar o `.env`.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8q_evidence_incidents.py"
```

## Testes

```powershell
python -m pytest -q tests\test_paper_certification_evidence_incidents.py
python -m pytest -q
```

Com os 136 testes anteriores, a expectativa é de 144 testes aprovados.

## Validação HTTP

Reinicie o servidor e execute:

```powershell
python ".\scripts\real_tests\phase8q_evidence_incidents_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```
