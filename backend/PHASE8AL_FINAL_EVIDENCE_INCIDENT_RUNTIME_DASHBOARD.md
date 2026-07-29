# PredArb — Fase 8AL: Dashboard do Runtime dos Incidentes Finais

A Fase 8AL adiciona uma interface operacional para o runtime criado na
Fase 8AK.

## Novas rotas

- `GET /paper/final-validation/evidence/incident-runtime/dashboard`
- `GET /paper/final-validation/evidence/incident-runtime/snapshot`

## Recursos

- estado do runtime;
- status e score do monitor;
- ciclos, sucessos e falhas;
- incidentes ativos e críticos;
- incidentes criados e resolvidos pelo runtime;
- início com intervalo configurável;
- parada manual;
- captura imediata;
- reset das estatísticas;
- visualização do último ciclo.

## Segurança

- abrir o dashboard não inicia o runtime;
- o snapshot não captura o monitor;
- todas as ações administrativas exigem confirmação;
- o intervalo mínimo pela API é de 30 segundos;
- somente o diário de incidentes é atualizado;
- o arquivo probatório não é modificado;
- a próxima fase não é autorizada;
- execução live e financeira permanecem bloqueadas.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8al_final_evidence_incident_runtime_dashboard.py"
```

## Testes

```powershell
python -m pytest -q tests\test_final_paper_validation_evidence_incident_runtime_dashboard.py
python -m pytest -q
```

Com os 293 testes anteriores, a expectativa é de 299 testes aprovados.

## Validação HTTP

```powershell
python ".\scripts\real_tests\phase8al_final_evidence_incident_runtime_dashboard_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Dashboard:

```text
http://127.0.0.1:8000/paper/final-validation/evidence/incident-runtime/dashboard
```
