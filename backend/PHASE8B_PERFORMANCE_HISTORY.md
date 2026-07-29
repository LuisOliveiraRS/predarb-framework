# PredArb — Fase 8B: histórico e métricas consolidadas

A Fase 8B transforma os relatórios produzidos pela sessão prolongada em uma
camada de consulta somente leitura.

## Novos endpoints

- `GET /paper/performance/health`
- `GET /paper/performance/summary`
- `GET /paper/performance/reports`
- `GET /paper/performance/history`
- `GET /paper/performance/reports/{report_name}`

## Segurança

Nenhum endpoint desta fase envia ordens, inicia sessões ou altera a conta Paper.
As respostas declaram:

```json
{
  "execution_authorized": false,
  "live_execution": false
}
```

## Instalação

Depois de extrair o ZIP dentro do backend:

```powershell
python ".\scripts\real_tests\install_phase8b_performance.py"
```

## Testes

```powershell
python -m pytest -q tests\test_paper_performance.py
python -m pytest -q
```

Com os 28 testes anteriores, a expectativa é de 34 testes aprovados.

## Validação HTTP

Reinicie o servidor usando o script da Fase 8:

```powershell
& ".\scripts\real_tests\phase8_start_server.ps1"
```

Em outro terminal:

```powershell
python ".\scripts\real_tests\phase8b_performance_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```
