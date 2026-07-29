param(
    [string]$BackendRoot = "C:\predarb-framework\backend"
)

$ErrorActionPreference = "Stop"

$BackendRoot = (Resolve-Path $BackendRoot).Path
$Payload = Join-Path $BackendRoot "repair_payload\app\core\application.py"
$Target = Join-Path $BackendRoot "app\core\application.py"

if (-not (Test-Path $Payload)) {
    throw "Payload não encontrado: $Payload"
}

if (-not (Test-Path (Join-Path $BackendRoot "app\main.py"))) {
    throw "Backend inválido: app\main.py não encontrado em $BackendRoot"
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backup = Join-Path $BackendRoot "app\core\application_before_routes_repair_$stamp.py"
Copy-Item $Target $backup -Force
Copy-Item $Payload $Target -Force

Get-ChildItem -Path (Join-Path $BackendRoot "app") -Recurse -Directory -Filter "__pycache__" |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Set-Location $BackendRoot

Write-Host "Arquivo aplicado:" -ForegroundColor Cyan
Get-Item $Target | Select-Object FullName, Length, LastWriteTime

@'
import inspect
from fastapi.routing import APIRoute, APIWebSocketRoute
from starlette.routing import Mount
import app.core.application as direct
from app.core import application as via_package

print("Módulo direto:", direct.__file__)
print("Módulo via pacote:", via_package.__file__)
assert direct is via_package

source = inspect.getsource(direct.create_app)
assert "paper_router" in source
assert "ai_dashboard_ws_router" in source

app = direct.create_app()
http_paths = {r.path for r in app.routes if isinstance(r, APIRoute)}
ws_paths = {r.path for r in app.routes if isinstance(r, APIWebSocketRoute)}
mount_paths = {r.path for r in app.routes if isinstance(r, Mount)}

required = {
    "/paper/risk/status",
    "/paper/session/status",
    "/paper/session/report",
    "/paper/session/cycle",
    "/paper/session/start",
    "/paper/session/stop",
    "/paper/session/reset-report",
}
missing = sorted(required - http_paths)

print("Rotas HTTP:", len(http_paths))
print("WebSockets:", sorted(ws_paths))
print("Mounts:", sorted(mount_paths))
print("Ausentes:", missing)

assert not missing, missing
assert "/ws/router" in ws_paths
assert "/dashboard/static" in mount_paths
print("REPARO VALIDADO")
'@ | python

Write-Host "Backup: $backup" -ForegroundColor Yellow
Write-Host "Agora execute: python -m pytest -q" -ForegroundColor Green
