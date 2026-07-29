# PredArb — Fase 8J: Paper Readiness Gate

A Fase 8J adiciona um gate objetivo para avaliar se a operação Paper possui
dados, estabilidade e segurança suficientes para continuar os testes
prolongados.

## Status possíveis

- `READY`
- `NOT_READY`
- `INSUFFICIENT_DATA`

## Novas rotas

- `GET /paper/readiness/health`
- `GET /paper/readiness/report`
- `GET /paper/readiness/dashboard`
- `GET /paper/readiness/export.json`

## Checks

- quantidade mínima de relatórios;
- quantidade mínima de ciclos;
- quantidade mínima de trades Paper;
- zero violações de segurança;
- zero erros de endpoint;
- monitor fora de estado crítico;
- score mínimo do monitor;
- zero incidentes críticos ativos;
- warnings dentro do limite;
- falhas do runtime dentro do limite;
- execução financeira explicitamente bloqueada.

## Limites padrão

```env
PAPER_READINESS_MIN_REPORTS=2
PAPER_READINESS_MIN_CYCLES=20
PAPER_READINESS_MIN_TRADES=10
PAPER_READINESS_MIN_MONITOR_SCORE=75
PAPER_READINESS_MAX_ACTIVE_WARNING_INCIDENTS=5
PAPER_READINESS_MAX_RUNTIME_FAILURES=0
```

Não é necessário alterar o `.env`.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8j_readiness.py"
```

## Testes

```powershell
python -m pytest -q tests\test_paper_readiness.py
python -m pytest -q
```

Com os 81 testes anteriores, a expectativa é de 89 testes aprovados.

## Validação HTTP

Reinicie o servidor da Fase 8 e execute:

```powershell
python ".\scripts\real_tests\phase8j_readiness_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Dashboard:

```text
http://127.0.0.1:8000/paper/readiness/dashboard
```

Um resultado `INSUFFICIENT_DATA` não representa falha técnica. Ele apenas
indica que ainda é necessário acumular mais sessões, ciclos ou trades Paper.
