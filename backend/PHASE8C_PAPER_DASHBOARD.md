# PredArb — Fase 8C: dashboard Paper de desempenho

A Fase 8C adiciona uma interface web somente leitura sobre os dados consolidados
na Fase 8B.

## Novas rotas

- `GET /paper/performance/dashboard`
- `GET /paper/performance/snapshot`
- `GET /paper/performance/export.csv`

## Recursos

- cards de sessões, ciclos, trades e resultado;
- curva de equity em SVG;
- tabela das sessões;
- atualização automática a cada 15 segundos;
- exportação do histórico em CSV;
- nenhuma ação de compra, venda, execução ou início de sessão.

## Instalação

```powershell
python ".\scripts\real_tests\install_phase8c_dashboard.py"
```

## Testes

```powershell
python -m pytest -q tests\test_paper_performance_dashboard.py
python -m pytest -q
```

Com os 34 testes anteriores, a expectativa é de 39 testes aprovados.

## Validação HTTP

Reinicie o servidor da Fase 8 e execute, em outro terminal:

```powershell
python ".\scripts\real_tests\phase8c_dashboard_api_check.py" `
    --base-url "http://127.0.0.1:8000"
```

Abra no navegador:

```text
http://127.0.0.1:8000/paper/performance/dashboard
```
