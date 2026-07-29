# PredArb — Fase 8AU: Certificação da Qualificação Final Paper

A Fase 8AU consolida o Gate de Qualificação da Fase 8AQ, o histórico da
Fase 8AR e o runtime da Fase 8AS em uma certificação técnica final do
ambiente Paper.

## Estados

```text
CERTIFIED
PENDING
BLOCKED
NO_DATA
```

## Critérios padrão

- gate atual `QUALIFIED`;
- score atual do gate de pelo menos 90;
- pelo menos 3 registros no histórico do gate;
- último gate persistido `QUALIFIED`;
- último score persistido de pelo menos 90;
- score médio de pelo menos 90;
- sequência atual de pelo menos 3 estados `QUALIFIED`;
- nenhuma falha crítica no gate;
- nenhuma falha no runtime do histórico do gate.

## Rotas

- `GET /paper/final-assurance/qualification-certification/health`
- `GET /paper/final-assurance/qualification-certification/report`
- `GET /paper/final-assurance/qualification-certification/dashboard`
- `GET /paper/final-assurance/qualification-certification/export.json`

Todas as rotas são somente leitura.

## Significado de CERTIFIED

`CERTIFIED` significa apenas que os critérios técnicos consolidados do
ambiente Paper foram atendidos.

Não significa:

- autorização para execução live;
- autorização para uso de capital real;
- autorização para envio de ordens;
- inicialização automática de runtimes;
- autorização automática da próxima fase;
- autorização da IA para executar operações.

## Variáveis opcionais

```env
PAPER_FINAL_QUALIFICATION_CERTIFICATION_MIN_HISTORY_ENTRIES=3
PAPER_FINAL_QUALIFICATION_CERTIFICATION_MIN_STREAK=3
PAPER_FINAL_QUALIFICATION_CERTIFICATION_MIN_CURRENT_SCORE=90
PAPER_FINAL_QUALIFICATION_CERTIFICATION_MIN_AVERAGE_SCORE=90
PAPER_FINAL_QUALIFICATION_CERTIFICATION_MAX_RUNTIME_FAILURES=0
```

Não é necessário alterar o `.env`.

## Segurança

```json
{
  "scope": "PAPER_QUALIFICATION_CERTIFICATION_ONLY",
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
python ".\scripts\real_tests\install_phase8au_final_paper_assurance_qualification_certification.py"
```

## Testes

```powershell
python -m pytest -q tests\test_final_paper_assurance_qualification_certification.py
python -m pytest -q
```

A Fase 8AU adiciona 8 testes. Considerando os 361 testes anteriores, a
expectativa é de 369 testes aprovados.

## Validação HTTP

```powershell
python ".\scripts\real_tests\phase8au_final_paper_assurance_qualification_certification_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Dashboard:

```text
http://127.0.0.1:8000/paper/final-assurance/qualification-certification/dashboard
```
