# PredArb — Fase 8R: Dashboard dos Incidentes das Evidências

A Fase 8R adiciona uma interface operacional para o journal criado na Fase 8Q.

## Novas rotas

- `GET /paper/certification/evidence/incidents/ui/dashboard`
- `GET /paper/certification/evidence/incidents/ui/snapshot`
- `GET /paper/certification/evidence/incidents/ui/export.csv`

O prefixo `/ui` evita conflito com a rota dinâmica
`/paper/certification/evidence/incidents/{incident_id}`.

## Recursos

- resumo de incidentes ativos e resolvidos;
- contagem por severidade;
- estado atual do monitor;
- captura manual dos alertas;
- reconhecimento administrativo;
- histórico de ocorrências e reativações;
- exportação CSV;
- atualização automática a cada 10 segundos.

## Segurança

- o dashboard não captura implicitamente;
- o snapshot não altera o journal;
- todas as ações administrativas exigem confirmação;
- reconhecer não resolve nem remove um alerta;
- execução live e financeira continuam bloqueadas.

## Confirmações utilizadas

```text
CAPTURE-PAPER-EVIDENCE-INCIDENTS
ACK-PAPER-EVIDENCE-INCIDENT
```

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8r_evidence_incident_dashboard.py"
```

## Testes

```powershell
python -m pytest -q tests\test_paper_certification_evidence_incident_dashboard.py
python -m pytest -q
```

Com os 144 testes anteriores, a expectativa é de 151 testes aprovados.

## Validação HTTP

Reinicie o servidor e execute:

```powershell
python ".\scripts\real_tests\phase8r_evidence_incident_dashboard_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Dashboard:

```text
http://127.0.0.1:8000/paper/certification/evidence/incidents/ui/dashboard
```
