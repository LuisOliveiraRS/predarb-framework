# PredArb — Fase 8O: Arquivo de Evidências da Certificação

A Fase 8O registra avaliações da Certificação Paper em um arquivo persistente
com encadeamento SHA-256.

## Recursos

- captura manual e confirmada;
- hash SHA-256 para cada evidência;
- ligação com o hash da evidência anterior;
- verificação completa da cadeia;
- detecção de alteração dos registros;
- dashboard;
- exportação CSV;
- exportação JSON;
- gravação atômica;
- escopo estritamente `PAPER_ONLY`.

## Status de integridade

- `VALID`
- `BROKEN`
- `EMPTY`

## Novas rotas

- `GET /paper/certification/evidence/health`
- `GET /paper/certification/evidence/summary`
- `GET /paper/certification/evidence/verify`
- `GET /paper/certification/evidence/latest`
- `GET /paper/certification/evidence/entries`
- `GET /paper/certification/evidence/snapshot`
- `POST /paper/certification/evidence/capture`
- `GET /paper/certification/evidence/dashboard`
- `GET /paper/certification/evidence/export.csv`
- `GET /paper/certification/evidence/export.json`

## Confirmação obrigatória

```text
CAPTURE-PAPER-CERTIFICATION-EVIDENCE
```

## Arquivo persistente

```text
paper_data/paper_certification_evidence.json
```

Variável opcional:

```env
PAPER_CERTIFICATION_EVIDENCE_PATH=paper_data/paper_certification_evidence.json
```

Não é necessário alterar o `.env`.

## Segurança

Mesmo uma evidência com status `CERTIFIED` mantém:

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
python ".\scripts\real_tests\install_phase8o_certification_evidence.py"
```

## Testes

```powershell
python -m pytest -q tests\test_paper_certification_evidence.py
python -m pytest -q
```

Com os 120 testes anteriores, a expectativa é de 128 testes aprovados.

## Validação HTTP

Reinicie o servidor e execute:

```powershell
python ".\scripts\real_tests\phase8o_certification_evidence_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Dashboard:

```text
http://127.0.0.1:8000/paper/certification/evidence/dashboard
```
