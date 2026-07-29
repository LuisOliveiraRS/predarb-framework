# PredArb — Fase 8AC: Validação Final Paper

A Fase 8AC consolida o Centro de Garantia, o Gate de Qualificação, o histórico
do gate e os runtimes de captura em uma avaliação final somente leitura.

## Status possíveis

- `PAPER_VALIDATED`
- `PAPER_PENDING`
- `PAPER_BLOCKED`
- `INSUFFICIENT_DATA`

## Novas rotas

- `GET /paper/final-validation/health`
- `GET /paper/final-validation/report`
- `GET /paper/final-validation/dashboard`
- `GET /paper/final-validation/export.json`

Todas as rotas são `GET`.

## Critérios padrão

```env
PAPER_FINAL_VALIDATION_MIN_GATE_EVALUATIONS=3
PAPER_FINAL_VALIDATION_MIN_QUALIFIED_STREAK=3
PAPER_FINAL_VALIDATION_MIN_GATE_SCORE=90
PAPER_FINAL_VALIDATION_MIN_ASSURANCE_SCORE=90
PAPER_FINAL_VALIDATION_MAX_RUNTIME_FAILURES=0
```

Não é necessário alterar o `.env`.

## Significado de PAPER_VALIDATED

`PAPER_VALIDATED` significa que:

- o Centro de Garantia está `ASSURED`;
- o Gate atual está `QUALIFIED`;
- há avaliações históricas suficientes;
- existe sequência mínima de `QUALIFIED`;
- os scores atendem aos limites;
- não existem falhas de runtime acima do limite.

Esse status não autoriza:

- execução live;
- uso de capital real;
- ativação automática de workers;
- envio de ordens;
- mudança automática para a próxima fase;
- autorização da IA para executar operações.

## Segurança

```json
{
  "scope": "PAPER_VALIDATION_ONLY",
  "paper_execution_authorized": false,
  "live_authorization": false,
  "execution_authorized": false,
  "live_execution": false,
  "financial_execution": false,
  "next_step_authorized": false,
  "read_only": true
}
```

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8ac_final_paper_validation.py"
```

## Testes

```powershell
python -m pytest -q tests\test_final_paper_validation.py
python -m pytest -q
```

Com os 223 testes anteriores, a expectativa é de 231 testes aprovados.

## Validação HTTP

Reinicie o servidor e execute:

```powershell
python ".\scripts\real_tests\phase8ac_final_paper_validation_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Dashboard:

```text
http://127.0.0.1:8000/paper/final-validation/dashboard
```
