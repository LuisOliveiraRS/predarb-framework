# Compatibilidade de testes com FastAPI 0.137+

O FastAPI 0.137.0 mudou `app.routes` de uma lista plana para uma árvore de routers.
A API pública recomendada para enumerar todas as rotas é:

```python
from fastapi.routing import iter_route_contexts
```

## Aplicação

Dentro de `C:\predarb-framework\backend`:

```powershell
python ".\scripts\real_tests\fix_fastapi_0137_route_tests.py"
python ".\scripts\real_tests\phase7_router_definitions_check.py"
python -m pytest -q tests\test_application_integration.py tests\test_paper_risk_session.py
python -m pytest -q
```

O instalador cria backups dos dois arquivos de teste antes de modificá-los.
