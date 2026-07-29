# PredArb — Fase 8N: Certificação de Estabilidade Paper

A Fase 8N avalia a consistência do histórico de readiness e produz uma
certificação limitada exclusivamente ao ambiente Paper.

## Status possíveis

- `CERTIFIED`
- `PENDING`
- `BLOCKED`
- `NO_DATA`

## Novas rotas

- `GET /paper/certification/health`
- `GET /paper/certification/report`
- `GET /paper/certification/dashboard`
- `GET /paper/certification/export.json`

## Critérios padrão

```env
PAPER_CERTIFICATION_MIN_EVALUATIONS=5
PAPER_CERTIFICATION_MIN_CONSECUTIVE_READY=3
PAPER_CERTIFICATION_RECENT_WINDOW=5
PAPER_CERTIFICATION_MIN_LATEST_SCORE=80
PAPER_CERTIFICATION_MIN_RECENT_AVERAGE_SCORE=80
PAPER_CERTIFICATION_MAX_RECENT_NOT_READY=0
```

Não é necessário alterar o `.env`.

## Significado da certificação

`CERTIFIED` significa apenas que o histórico Paper atingiu os critérios de
estabilidade definidos. Isso não autoriza:

- execução live;
- envio de ordens;
- uso de capital real;
- autorização automática da IA;
- ativação de worker financeiro.

Todos os retornos mantêm:

```json
{
  "scope": "PAPER_ONLY",
  "paper_execution_authorized": false,
  "live_authorization": false,
  "execution_authorized": false,
  "live_execution": false,
  "financial_execution": false
}
```

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8n_stability_certification.py"
```

## Testes

```powershell
python -m pytest -q tests\test_paper_stability_certification.py
python -m pytest -q
```

Com os 112 testes anteriores, a expectativa é de 120 testes aprovados.

## Validação HTTP

Reinicie o servidor da Fase 8 e execute:

```powershell
python ".\scripts\real_tests\phase8n_stability_certification_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Dashboard:

```text
http://127.0.0.1:8000/paper/certification/dashboard
```
