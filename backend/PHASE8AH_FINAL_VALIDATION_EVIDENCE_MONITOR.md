# PredArb — Fase 8AH: Monitor das Evidências da Validação Final

A Fase 8AH adiciona um monitor somente leitura sobre o arquivo probatório
criado na Fase 8AG.

## Estados

```text
HEALTHY
WARNING
CRITICAL
NO_DATA
```

## Verificações

- quantidade mínima de evidências;
- integridade da cadeia SHA-256;
- presença do `chain_head`;
- escopo `PAPER_VALIDATION_ONLY`;
- status da evidência mais recente;
- idade da evidência mais recente;
- guardas financeiras e de próxima fase.

## Rotas

- `GET /paper/final-validation/evidence/monitor/health`
- `GET /paper/final-validation/evidence/monitor/alerts`
- `GET /paper/final-validation/evidence/monitor/score`
- `GET /paper/final-validation/evidence/monitor/snapshot`
- `GET /paper/final-validation/evidence/monitor/dashboard`
- `GET /paper/final-validation/evidence/monitor/export.json`

Todas as rotas são `GET` e somente leitura.

## Variáveis opcionais

```env
PAPER_FINAL_EVIDENCE_MONITOR_STALE_HOURS=72
PAPER_FINAL_EVIDENCE_MONITOR_MIN_ENTRIES=1
```

Não é necessário alterar o `.env`.

## Pontuação

- alerta crítico: menos 40 pontos;
- warning: menos 15 pontos;
- informativo: menos 5 pontos;
- qualquer crítico limita o score a 49;
- qualquer warning limita o score a 79;
- ausência de dados resulta em score 0.

## Segurança

- nenhuma captura de evidência;
- nenhuma alteração no arquivo probatório;
- nenhuma inicialização de runtime;
- nenhuma autorização da próxima fase;
- nenhuma execução financeira ou live;
- falha fechada para payloads inseguros.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8ah_final_validation_evidence_monitor.py"
```

## Testes

```powershell
python -m pytest -q tests\test_final_paper_validation_evidence_monitor.py
python -m pytest -q
```

Com os 262 testes anteriores, a expectativa é de 270 testes aprovados.

## Validação HTTP

```powershell
python ".\scripts\real_tests\phase8ah_final_validation_evidence_monitor_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Dashboard:

```text
http://127.0.0.1:8000/paper/final-validation/evidence/monitor/dashboard
```
