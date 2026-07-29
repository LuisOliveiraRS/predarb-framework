# PredArb — Fase 8T: Dashboard do Runtime dos Incidentes das Evidências

A Fase 8T adiciona uma interface operacional para controlar e acompanhar o
runtime criado na Fase 8S.

## Novas rotas

- `GET /paper/certification/evidence/incident-runtime/dashboard`
- `GET /paper/certification/evidence/incident-runtime/snapshot`

## Recursos

- estado atual do runtime;
- status e score do monitor de evidências;
- total de ciclos, sucessos e falhas;
- incidentes ativos;
- snapshots do journal;
- início com intervalo configurável;
- parada manual;
- captura imediata;
- reset apenas das estatísticas;
- visualização do último ciclo.

## Segurança

- o snapshot não inicia o runtime;
- nenhuma captura ocorre ao abrir o dashboard;
- todas as ações exigem confirmação;
- intervalo mínimo de 30 segundos;
- nenhuma evidência ou certificação é criada;
- execução live e financeira continuam bloqueadas.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8t_evidence_incident_runtime_dashboard.py"
```

## Testes

```powershell
python -m pytest -q tests\test_paper_certification_evidence_incident_runtime_dashboard.py
python -m pytest -q
```

Com os 159 testes anteriores, a expectativa é de 165 testes aprovados.

## Validação HTTP

Reinicie o servidor e execute:

```powershell
python ".\scripts\real_tests\phase8t_evidence_incident_runtime_dashboard_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Dashboard:

```text
http://127.0.0.1:8000/paper/certification/evidence/incident-runtime/dashboard
```
