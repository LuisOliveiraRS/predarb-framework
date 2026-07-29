# PredArb — Fase 8AM: Garantia Operacional Final Paper

A Fase 8AM consolida a validação final, o histórico, a cadeia probatória, o
monitor das evidências, o diário de incidentes e os runtimes finais.

## Estados

```text
ASSURED
WARNING
BLOCKED
NO_DATA
```

## Componentes avaliados

- Validação Final Paper;
- histórico da validação final;
- runtime do histórico;
- evidências SHA-256;
- integridade probatória;
- monitor das evidências;
- diário de incidentes;
- runtime dos incidentes.

## Novas rotas

- `GET /paper/final-assurance/health`
- `GET /paper/final-assurance/report`
- `GET /paper/final-assurance/dashboard`
- `GET /paper/final-assurance/export.json`

Todas as rotas são `GET` e somente leitura.

## Significado de ASSURED

`ASSURED` significa somente que os componentes finais do ambiente Paper
atenderam aos critérios técnicos consolidados.

Não significa:

- autorização para execução live;
- autorização para uso de capital real;
- autorização para envio de ordens;
- ativação automática de runtimes;
- autorização automática da próxima fase;
- autorização da IA para executar operações.

## Regras gerais

- `BLOCKED`: falha de componente, validação bloqueada, cadeia quebrada,
  monitor crítico ou incidente crítico ativo.
- `NO_DATA`: histórico, evidências ou validação final ainda insuficientes.
- `WARNING`: há alertas não críticos, incidentes ativos ou falhas de runtime.
- `ASSURED`: todos os critérios foram aprovados.

Os runtimes não precisam estar executando. O início manual é uma proteção
intencional.

## Segurança

```json
{
  "scope": "PAPER_ASSURANCE_ONLY",
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
python ".\scripts\real_tests\install_phase8am_final_paper_operational_assurance.py"
```

## Testes

```powershell
python -m pytest -q tests\test_final_paper_operational_assurance.py
python -m pytest -q
```

Com os 299 testes anteriores, a expectativa é de 307 testes aprovados.

## Validação HTTP

Reinicie o servidor e execute:

```powershell
python ".\scripts\real_tests\phase8am_final_paper_operational_assurance_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Dashboard:

```text
http://127.0.0.1:8000/paper/final-assurance/dashboard
```
