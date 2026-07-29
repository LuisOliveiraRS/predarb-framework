# PredArb — Fase 8F: dashboard operacional de incidentes

A Fase 8F adiciona uma interface web para consultar e administrar o journal
criado na Fase 8E.

## Novas rotas

- `GET /paper/performance/incidents/dashboard`
- `GET /paper/performance/incidents/snapshot`
- `GET /paper/performance/incidents/export.csv`

As ações administrativas usam os endpoints já existentes:

- `POST /paper/performance/incidents/capture`
- `POST /paper/performance/incidents/{incident_id}/acknowledge`

## Recursos

- resumo de incidentes ativos, críticos, resolvidos e reconhecidos;
- integração visual com o monitor da Fase 8D;
- captura manual com confirmação;
- reconhecimento de incidentes;
- histórico recente;
- exportação CSV;
- nenhuma execução financeira.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8f_incident_dashboard.py"
```

## Testes

```powershell
python -m pytest -q tests\test_paper_performance_incident_dashboard.py
python -m pytest -q
```

Com os 54 testes anteriores, a expectativa é de 60 testes aprovados.

## Validação HTTP

Reinicie o servidor da Fase 8 e execute:

```powershell
python ".\scripts\real_tests\phase8f_incident_dashboard_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Dashboard:

```text
http://127.0.0.1:8000/paper/performance/incidents/dashboard
```
