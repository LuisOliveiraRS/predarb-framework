# PredArb — reparo das definições de rotas da Fase 7

Este pacote restaura somente:

- `app/api/routers/paper.py`
- `app/dashboard/router_ws.py`
- `scripts/real_tests/phase7_router_definitions_check.py`

O `application.py` não é alterado. O reparo é destinado ao caso em que o
`application.py` está correto, mas os objetos `paper_router` e `router_ws`
foram importados de arquivos vazios ou antigos.
