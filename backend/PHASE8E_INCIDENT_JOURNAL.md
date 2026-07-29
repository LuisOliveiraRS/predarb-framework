# PredArb — Fase 8E: journal persistente de incidentes

A Fase 8E transforma os alertas temporários da Fase 8D em um histórico
persistente de incidentes operacionais.

## Recursos

- criação automática de incidente por alerta;
- identificação determinística por código, severidade e título;
- contagem de recorrências;
- resolução quando o alerta desaparece;
- reativação se o alerta retornar;
- reconhecimento manual do incidente;
- snapshots históricos do monitor;
- gravação atômica em JSON;
- execução live permanentemente bloqueada.

## Novas rotas

- `GET /paper/performance/incidents/health`
- `GET /paper/performance/incidents/summary`
- `GET /paper/performance/incidents/active`
- `GET /paper/performance/incidents/history`
- `GET /paper/performance/incidents/snapshots`
- `POST /paper/performance/incidents/capture`
- `POST /paper/performance/incidents/{incident_id}/acknowledge`

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8e_incidents.py"
```

## Testes

```powershell
python -m pytest -q tests\test_paper_performance_incidents.py
python -m pytest -q
```

Com os 46 testes anteriores, a expectativa é de 54 testes aprovados.

## Validação HTTP

Reinicie o servidor da Fase 8 e execute:

```powershell
python ".\scripts\real_tests\phase8e_incidents_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

## Arquivo persistente

O padrão é:

```text
paper_data/paper_monitor_incidents.json
```

Opcionalmente:

```env
PAPER_MONITOR_INCIDENTS_PATH=paper_data/paper_monitor_incidents.json
```
