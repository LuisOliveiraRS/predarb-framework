# PredArb — Fase 8P: Monitor de Integridade das Evidências

A Fase 8P adiciona um monitor somente leitura sobre o arquivo encadeado criado
na Fase 8O.

## Status possíveis

- `HEALTHY`
- `WARNING`
- `CRITICAL`
- `NO_DATA`

## Verificações

- integridade da cadeia SHA-256;
- quantidade mínima de evidências;
- escopo `PAPER_ONLY`;
- guardas de execução explicitamente bloqueadas;
- idade da evidência mais recente;
- status da certificação mais recente;
- validade do chain head.

## Novas rotas

- `GET /paper/certification/evidence/monitor/health`
- `GET /paper/certification/evidence/monitor/alerts`
- `GET /paper/certification/evidence/monitor/score`
- `GET /paper/certification/evidence/monitor/snapshot`
- `GET /paper/certification/evidence/monitor/dashboard`
- `GET /paper/certification/evidence/monitor/export.json`

Todas as rotas são `GET`.

## Limites padrão

```env
PAPER_EVIDENCE_MONITOR_STALE_HOURS=72
PAPER_EVIDENCE_MONITOR_MIN_ENTRIES=1
```

Não é necessário alterar o `.env`.

## Segurança

O monitor:

- não cria evidências;
- não altera o arquivo;
- não captura certificações;
- não inicia runtimes;
- não executa ordens;
- não autoriza execução live.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8p_evidence_monitor.py"
```

## Testes

```powershell
python -m pytest -q tests\test_paper_certification_evidence_monitor.py
python -m pytest -q
```

Com os 128 testes anteriores, a expectativa é de 136 testes aprovados.

## Validação HTTP

Reinicie o servidor e execute:

```powershell
python ".\scripts\real_tests\phase8p_evidence_monitor_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Dashboard:

```text
http://127.0.0.1:8000/paper/certification/evidence/monitor/dashboard
```
