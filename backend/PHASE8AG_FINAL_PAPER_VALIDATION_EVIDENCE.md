# PredArb — Fase 8AG: Evidências da Validação Final Paper

A Fase 8AG cria um arquivo probatório persistente e encadeado por SHA-256 para
as avaliações da Validação Final Paper.

## Integridade

Cada entrada contém `previous_hash`, `entry_hash`, status, score, garantia,
gate, sequência `QUALIFIED`, falhas de runtime e códigos dos critérios
reprovados.

A cadeia é verificada do início ao fim. Alterações manuais tornam o estado
`BROKEN` e bloqueiam novas capturas.

## Estados

```text
EMPTY
VALID
BROKEN
```

## Rotas

- `GET /paper/final-validation/evidence/health`
- `GET /paper/final-validation/evidence/summary`
- `GET /paper/final-validation/evidence/verify`
- `GET /paper/final-validation/evidence/latest`
- `GET /paper/final-validation/evidence/entries`
- `GET /paper/final-validation/evidence/snapshot`
- `POST /paper/final-validation/evidence/capture`
- `GET /paper/final-validation/evidence/dashboard`
- `GET /paper/final-validation/evidence/export.csv`
- `GET /paper/final-validation/evidence/export.json`

## Confirmação

```text
CAPTURE-FINAL-PAPER-VALIDATION-EVIDENCE
```

## Persistência

```text
paper_data/final_paper_validation_evidence.json
```

Variável opcional:

```env
PAPER_FINAL_VALIDATION_EVIDENCE_PATH=paper_data/final_paper_validation_evidence.json
```

A cadeia não é truncada automaticamente. Ao atingir o limite, novas capturas
são bloqueadas para preservar a integridade histórica.

## Segurança

- captura manual e confirmada;
- nenhuma autorização da próxima fase;
- nenhuma execução live ou financeira;
- nenhuma ordem;
- leitura fail-closed;
- gravação JSON atômica;
- bloqueio local por `RLock`.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8ag_final_paper_validation_evidence.py"
```

## Testes

```powershell
python -m pytest -q tests\test_final_paper_validation_evidence.py
python -m pytest -q
```

Com os 253 testes anteriores, a expectativa é de 262 testes aprovados.

## Validação HTTP

```powershell
python ".\scripts\real_tests\phase8ag_final_paper_validation_evidence_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Dashboard:

```text
http://127.0.0.1:8000/paper/final-validation/evidence/dashboard
```
