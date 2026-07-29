# PredArb — Fase 8AJ: Dashboard dos Incidentes das Evidências Finais

A Fase 8AJ adiciona uma interface operacional para o diário de incidentes
criado na Fase 8AI.

## Novas rotas

As rotas usam o segmento `/ui` para não serem confundidas com a rota dinâmica
`/{incident_id}` da Fase 8AI.

- `GET /paper/final-validation/evidence/incidents/ui/dashboard`
- `GET /paper/final-validation/evidence/incidents/ui/snapshot`
- `GET /paper/final-validation/evidence/incidents/ui/export.csv`

## Recursos

- status e score do monitor;
- incidentes ativos e resolvidos;
- contagem por severidade;
- incidentes reconhecidos e não reconhecidos;
- snapshots acumulados;
- tabela de incidentes ativos;
- histórico completo;
- captura manual do monitor;
- reconhecimento administrativo;
- exportação CSV.

## Segurança

- abrir o dashboard não captura o monitor;
- o snapshot é somente leitura;
- captura e reconhecimento exigem confirmação explícita;
- o reconhecimento não resolve o incidente;
- nenhuma alteração ocorre no arquivo probatório;
- nenhuma autorização da próxima fase;
- nenhuma execução live ou financeira.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8aj_final_evidence_incident_dashboard.py"
```

## Testes

```powershell
python -m pytest -q tests\test_final_paper_validation_evidence_incidents_dashboard.py
python -m pytest -q
```

Com os 279 testes anteriores, a expectativa é de 285 testes aprovados.

## Validação HTTP

```powershell
python ".\scripts\real_tests\phase8aj_final_evidence_incident_dashboard_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Dashboard:

```text
http://127.0.0.1:8000/paper/final-validation/evidence/incidents/ui/dashboard
```
