# Hotfix do teste WebSocket — FastAPI 0.139.2

Nesta versão, `RouteContext.path` pode ficar vazio para WebSockets vindos de
routers incluídos. O caminho efetivo está no `starlette_route` construído pelo
contexto de inclusão.

## Aplicação

Dentro de `C:\predarb-framework\backend`:

```powershell
python ".\scripts\real_tests\fix_fastapi_websocket_route_test.py"
python ".\scripts\real_tests\inspect_effective_websocket_routes.py"

python -m pytest `
    -q `
    tests\test_application_integration.py `
    tests\test_paper_risk_session.py

python -m pytest -q
```

O hotfix altera somente a função de teste
`test_application_has_no_duplicate_routes`.
