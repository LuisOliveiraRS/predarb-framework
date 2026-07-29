import pytest
from fastapi.routing import APIRoute, APIWebSocketRoute
from starlette.routing import Mount

from app.core import application
from app.core.settings import settings


def test_application_has_no_duplicate_routes():
    from fastapi.routing import (
        APIRoute,
        APIWebSocketRoute,
        iter_route_contexts,
    )
    from starlette.routing import Mount

    def effective_path(context):
        path = context.path
        if path:
            return path

        effective_route = getattr(
            context,
            "_effective_route",
            None,
        )

        starlette_route = getattr(
            effective_route,
            "starlette_route",
            None,
        )

        starlette_path = getattr(
            starlette_route,
            "path",
            None,
        )

        if starlette_path:
            return starlette_path

        return getattr(
            context.original_route,
            "path",
            "",
        )

    app = application.create_app()
    seen = set()

    for context in iter_route_contexts(app.routes):
        original_route = context.original_route
        path = effective_path(context)

        if isinstance(original_route, APIRoute):
            key = (
                path,
                tuple(sorted(context.methods or ())),
            )
        elif isinstance(original_route, APIWebSocketRoute):
            key = (
                path,
                ("WEBSOCKET",),
            )
        elif isinstance(original_route, Mount):
            key = (
                path,
                ("MOUNT",),
            )
        else:
            continue

        assert key not in seen, key
        seen.add(key)

    assert ("/dashboard/static", ("MOUNT",)) in seen
    assert ("/ws/router", ("WEBSOCKET",)) in seen




@pytest.mark.asyncio
async def test_offline_lifespan_starts_without_network(monkeypatch):
    monkeypatch.setattr(application, "initialize_database", lambda: None)
    monkeypatch.setattr(application.plugin_manager, "load", lambda: {})
    monkeypatch.setattr(application.plugin_manager, "stop", lambda: {})

    for name in (
        "MOCK_CONNECTOR_ENABLED",
        "HYPERLIQUID_CONNECTOR_ENABLED",
        "INITIAL_MARKET_SYNC_ENABLED",
        "SCHEDULER_ENABLED",
        "EXECUTION_WORKER_ENABLED",
        "ROUTER_DASHBOARD_ENABLED",
    ):
        monkeypatch.setattr(settings, name, False)

    app = application.create_app()

    async with app.router.lifespan_context(app):
        assert app.state.startup_completed is True
        assert app.state.initial_market_count == 0
        assert app.state.connector_startup == {}
        assert app.state.lifecycle["ai"] is True
        assert app.state.lifecycle["scheduler"] is False

    assert app.state.startup_completed is False
