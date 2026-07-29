# PredArb — Fase 8AQ: Gate de Qualificação da Garantia Final Paper

A Fase 8AQ qualifica a estabilidade técnica do ambiente Paper usando a
Garantia Operacional Final da Fase 8AM, o histórico da Fase 8AN e o runtime da
Fase 8AO.

## Estados

```text
QUALIFIED
PENDING
BLOCKED
NO_DATA
```

## Critérios padrão

- garantia atual `ASSURED`;
- score atual mínimo de 90;
- pelo menos 3 avaliações no histórico;
- última avaliação `ASSURED`;
- último score mínimo de 90;
- score médio mínimo de 90;
- sequência atual mínima de 3 avaliações `ASSURED`;
- integridade `VALID`;
- monitor `HEALTHY`;
- nenhum incidente ativo;
- nenhum incidente crítico ativo;
- nenhum erro de componente;
- nenhuma falha acumulada de runtime.

## Rotas

- `GET /paper/final-assurance/qualification-gate/health`
- `GET /paper/final-assurance/qualification-gate/report`
- `GET /paper/final-assurance/qualification-gate/dashboard`
- `GET /paper/final-assurance/qualification-gate/export.json`

Todas as rotas são somente leitura.

## Variáveis opcionais

```env
PAPER_FINAL_ASSURANCE_GATE_MIN_HISTORY_ENTRIES=3
PAPER_FINAL_ASSURANCE_GATE_MIN_ASSURED_STREAK=3
PAPER_FINAL_ASSURANCE_GATE_MIN_CURRENT_SCORE=90
PAPER_FINAL_ASSURANCE_GATE_MIN_AVERAGE_SCORE=90
PAPER_FINAL_ASSURANCE_GATE_MAX_RUNTIME_FAILURES=0
```

## Segurança

`QUALIFIED` não autoriza execução live, uso de capital real, envio de ordens,
inicialização automática de runtime ou avanço automático de fase.

```json
{
  "scope": "PAPER_ASSURANCE_QUALIFICATION_ONLY",
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
python ".\scripts\real_tests\install_phase8aq_final_paper_assurance_qualification_gate.py"
```

## Testes

```powershell
python -m pytest -q tests\test_final_paper_assurance_qualification_gate.py
python -m pytest -q
```

A Fase 8AQ adiciona 8 testes. Considerando os 330 testes anteriores, a
expectativa é de 338 testes aprovados.

## Validação HTTP

```powershell
python ".\scripts\real_tests\phase8aq_final_paper_assurance_qualification_gate_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Dashboard:

```text
http://127.0.0.1:8000/paper/final-assurance/qualification-gate/dashboard
```
