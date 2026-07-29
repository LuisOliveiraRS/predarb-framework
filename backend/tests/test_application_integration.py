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
        assert (
            app.state.lifecycle[
                "shadow_runtime_scheduler"
            ]
            is False
        )

    assert app.state.startup_completed is False


@pytest.mark.asyncio
async def test_lifespan_keeps_shadow_scheduler_disabled_by_default(
    monkeypatch,
):
    monkeypatch.setattr(
        application,
        "initialize_database",
        lambda: None,
    )
    monkeypatch.setattr(
        application.plugin_manager,
        "load",
        lambda: {},
    )
    monkeypatch.setattr(
        application.plugin_manager,
        "stop",
        lambda: {},
    )

    for name in (
        "MOCK_CONNECTOR_ENABLED",
        "HYPERLIQUID_CONNECTOR_ENABLED",
        "INITIAL_MARKET_SYNC_ENABLED",
        "EXECUTION_WORKER_ENABLED",
        "ROUTER_DASHBOARD_ENABLED",
    ):
        monkeypatch.setattr(
            settings,
            name,
            False,
        )

    monkeypatch.setattr(
        settings,
        "SCHEDULER_ENABLED",
        True,
    )
    monkeypatch.setattr(
        settings,
        "SHADOW_RUNTIME_ENABLED",
        True,
    )
    monkeypatch.setattr(
        settings,
        "SHADOW_RUNTIME_SCHEDULER_ENABLED",
        False,
    )

    registered_jobs = []
    scheduler_events = []

    def fake_add_job(
        func,
        seconds,
        *,
        job_id=None,
        replace_existing=True,
        **kwargs,
    ):
        registered_jobs.append(
            {
                "func": func,
                "seconds": seconds,
                "job_id": job_id,
                "replace_existing": replace_existing,
                "kwargs": kwargs,
            }
        )

        return registered_jobs[-1]

    monkeypatch.setattr(
        application.scheduler_service,
        "add_job",
        fake_add_job,
    )
    monkeypatch.setattr(
        application.scheduler_service,
        "start",
        lambda: scheduler_events.append(
            "start"
        ) or True,
    )
    monkeypatch.setattr(
        application.scheduler_service,
        "shutdown",
        lambda: scheduler_events.append(
            "shutdown"
        ) or True,
    )

    app = application.create_app()

    async with app.router.lifespan_context(
        app
    ):
        assert [
            job["job_id"]
            for job in registered_jobs
        ] == [
            "market_update_task",
        ]

        assert (
            app.state.lifecycle[
                "scheduler"
            ]
            is True
        )
        assert (
            app.state.lifecycle[
                "shadow_runtime_scheduler"
            ]
            is False
        )
        assert (
            application
            .shadow_execution_runtime
            .status()[
                "scheduler_connected"
            ]
            is False
        )

    assert scheduler_events == [
        "start",
        "shutdown",
    ]
    assert (
        application
        .shadow_execution_runtime
        .status()[
            "scheduler_connected"
        ]
        is False
    )


@pytest.mark.asyncio
async def test_lifespan_registers_opt_in_shadow_job(
    monkeypatch,
):
    monkeypatch.setattr(
        application,
        "initialize_database",
        lambda: None,
    )
    monkeypatch.setattr(
        application.plugin_manager,
        "load",
        lambda: {},
    )
    monkeypatch.setattr(
        application.plugin_manager,
        "stop",
        lambda: {},
    )

    for name in (
        "MOCK_CONNECTOR_ENABLED",
        "HYPERLIQUID_CONNECTOR_ENABLED",
        "INITIAL_MARKET_SYNC_ENABLED",
        "EXECUTION_WORKER_ENABLED",
        "ROUTER_DASHBOARD_ENABLED",
    ):
        monkeypatch.setattr(
            settings,
            name,
            False,
        )

    monkeypatch.setattr(
        settings,
        "SCHEDULER_ENABLED",
        True,
    )
    monkeypatch.setattr(
        settings,
        "SHADOW_RUNTIME_ENABLED",
        True,
    )
    monkeypatch.setattr(
        settings,
        "SHADOW_RUNTIME_SCHEDULER_ENABLED",
        True,
    )
    monkeypatch.setattr(
        settings,
        "MARKET_UPDATE_INTERVAL_SECONDS",
        10,
    )
    monkeypatch.setattr(
        settings,
        "SHADOW_RUNTIME_INTERVAL_SECONDS",
        60,
    )

    registered_jobs = []
    scheduler_events = []

    def fake_add_job(
        func,
        seconds,
        *,
        job_id=None,
        replace_existing=True,
        **kwargs,
    ):
        registered_jobs.append(
            {
                "func": func,
                "seconds": seconds,
                "job_id": job_id,
                "replace_existing": replace_existing,
                "kwargs": kwargs,
            }
        )

        return registered_jobs[-1]

    monkeypatch.setattr(
        application.scheduler_service,
        "add_job",
        fake_add_job,
    )
    monkeypatch.setattr(
        application.scheduler_service,
        "start",
        lambda: scheduler_events.append(
            "start"
        ) or True,
    )
    monkeypatch.setattr(
        application.scheduler_service,
        "shutdown",
        lambda: scheduler_events.append(
            "shutdown"
        ) or True,
    )

    app = application.create_app()

    async with app.router.lifespan_context(
        app
    ):
        jobs_by_id = {
            job["job_id"]: job
            for job in registered_jobs
        }

        assert set(
            jobs_by_id
        ) == {
            "market_update_task",
            "shadow_runtime_task",
        }

        assert (
            jobs_by_id[
                "market_update_task"
            ][
                "func"
            ]
            is application.market_update_task
        )
        assert (
            jobs_by_id[
                "market_update_task"
            ][
                "seconds"
            ]
            == 10
        )

        assert (
            jobs_by_id[
                "shadow_runtime_task"
            ][
                "func"
            ]
            is application.shadow_runtime_task
        )
        assert (
            jobs_by_id[
                "shadow_runtime_task"
            ][
                "seconds"
            ]
            == 60
        )

        assert (
            app.state.lifecycle[
                "shadow_runtime_scheduler"
            ]
            is True
        )
        assert (
            application
            .shadow_execution_runtime
            .status()[
                "scheduler_connected"
            ]
            is True
        )

    assert scheduler_events == [
        "start",
        "shutdown",
    ]
    assert (
        app.state.lifecycle[
            "shadow_runtime_scheduler"
        ]
        is False
    )
    assert (
        application
        .shadow_execution_runtime
        .status()[
            "scheduler_connected"
        ]
        is False
    )
