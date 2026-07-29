# PredArb — Fase 8U: Centro de Garantia da Certificação Paper

A Fase 8U consolida certificação, evidências, integridade, incidentes e runtime
em uma única visão operacional somente leitura.

## Status possíveis

- `ASSURED`
- `WARNING`
- `PENDING`
- `BLOCKED`
- `CRITICAL`
- `UNKNOWN`

## Novas rotas

- `GET /paper/certification/assurance/health`
- `GET /paper/certification/assurance/snapshot`
- `GET /paper/certification/assurance/dashboard`
- `GET /paper/certification/assurance/export.json`

Todas as rotas são `GET`.

## Componentes consolidados

- Certificação Paper da Fase 8N;
- arquivo de evidências da Fase 8O;
- monitor de integridade da Fase 8P;
- journal de incidentes da Fase 8Q;
- runtime de incidentes da Fase 8S.

## Significado de ASSURED

`ASSURED` significa que:

- a certificação atual está `CERTIFIED`;
- o monitor está `HEALTHY`;
- a cadeia de evidências está válida;
- não existem incidentes críticos ativos.

Isso continua restrito ao ambiente Paper e não autoriza execução live.

## Segurança

```json
{
  "scope": "PAPER_ONLY",
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
python ".\scripts\real_tests\install_phase8u_certification_assurance.py"
```

## Testes

```powershell
python -m pytest -q tests\test_paper_certification_assurance.py
python -m pytest -q
```

Com os 165 testes anteriores, a expectativa é de 172 testes aprovados.

## Validação HTTP

Reinicie o servidor e execute:

```powershell
python ".\scripts\real_tests\phase8u_certification_assurance_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Dashboard:

```text
http://127.0.0.1:8000/paper/certification/assurance/dashboard
```
