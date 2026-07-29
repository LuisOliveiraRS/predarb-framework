# PredArb — Fase 8I: Centro de Operações Paper

A Fase 8I consolida os módulos das fases 8B a 8H em uma visão operacional
única e somente leitura.

## Novas rotas

- `GET /paper/operations/health`
- `GET /paper/operations/snapshot`
- `GET /paper/operations/dashboard`
- `GET /paper/operations/export.json`

## Dados consolidados

- desempenho e equity;
- score e estado do monitor;
- incidentes ativos e resolvidos;
- estado e estatísticas do runtime;
- links para todos os dashboards;
- status operacional global.

## Status global

- `HEALTHY`
- `WARNING`
- `CRITICAL`
- `NO_DATA`
- `UNKNOWN`

## Segurança

- todas as rotas são `GET`;
- nenhum ciclo é iniciado pelo centro;
- nenhum incidente é capturado implicitamente;
- nenhuma ordem é executada;
- execução live e financeira permanecem bloqueadas;
- o runtime continua exigindo início manual.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8i_operations_center.py"
```

## Testes

```powershell
python -m pytest -q tests\test_paper_operations_center.py
python -m pytest -q
```

Com os 74 testes anteriores, a expectativa é de 81 testes aprovados.

## Validação HTTP

Reinicie o servidor da Fase 8 e execute:

```powershell
python ".\scripts\real_tests\phase8i_operations_center_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Dashboard:

```text
http://127.0.0.1:8000/paper/operations/dashboard
```
