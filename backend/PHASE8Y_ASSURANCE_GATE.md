# PredArb — Fase 8Y: Gate de Qualificação do Centro de Garantia Paper

A Fase 8Y avalia se o histórico do Centro de Garantia demonstra estabilidade
sustentada suficiente para receber o status `QUALIFIED`.

## Status possíveis

- `QUALIFIED`
- `NOT_QUALIFIED`
- `INSUFFICIENT_DATA`

## Novas rotas

- `GET /paper/certification/assurance/gate/health`
- `GET /paper/certification/assurance/gate/report`
- `GET /paper/certification/assurance/gate/dashboard`
- `GET /paper/certification/assurance/gate/export.json`

Todas as rotas são `GET` e somente leitura.

## Critérios padrão

```env
PAPER_ASSURANCE_GATE_MIN_ENTRIES=5
PAPER_ASSURANCE_GATE_MIN_ASSURED_STREAK=3
PAPER_ASSURANCE_GATE_RECENT_WINDOW=5
PAPER_ASSURANCE_GATE_MIN_LATEST_SCORE=85
PAPER_ASSURANCE_GATE_MIN_RECENT_AVERAGE_SCORE=80
PAPER_ASSURANCE_GATE_MAX_RECENT_WARNING=1
PAPER_ASSURANCE_GATE_MAX_RECENT_BLOCKED=0
PAPER_ASSURANCE_GATE_MAX_RECENT_CRITICAL=0
```

Não é necessário alterar o `.env`.

## Significado de QUALIFIED

`QUALIFIED` significa apenas que o histórico do Centro de Garantia atingiu os
critérios definidos para estabilidade sustentada.

Isso não autoriza:

- execução live;
- envio de ordens;
- uso de capital real;
- ativação automática de workers;
- autorização da IA para executar operações;
- mudança do projeto para produção financeira.

## Segurança

```json
{
  "scope": "PAPER_ASSURANCE_ONLY",
  "paper_execution_authorized": false,
  "live_authorization": false,
  "execution_authorized": false,
  "live_execution": false,
  "financial_execution": false,
  "read_only": true
}
```

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8y_assurance_gate.py"
```

## Testes

```powershell
python -m pytest -q tests\test_paper_certification_assurance_gate.py
python -m pytest -q
```

Com os 193 testes anteriores, a expectativa é de 201 testes aprovados.

## Validação HTTP

Reinicie o servidor e execute:

```powershell
python ".\scripts\real_tests\phase8y_assurance_gate_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Dashboard:

```text
http://127.0.0.1:8000/paper/certification/assurance/gate/dashboard
```
