import asyncio
import pytest
import ast
from pathlib import Path

from app.paper.shadow_execution_runtime import (
    PROTECTED_FALSE_FLAGS,
    ShadowExecutionRuntime,
)


from app.api.routers.shadow_execution_runtime import (
    shadow_runtime_architecture,
    shadow_runtime_health,
    shadow_runtime_metrics,
    shadow_runtime_status,
    router as shadow_runtime_router,
)
from app.core.application import create_app

SAFE_FLAGS = {
    "market_data_only": True,
    "read_only_market_access": True,
    "shadow_execution": True,
    "simulation_only": True,
    "paper_execution_authorized": False,
    "live_authorization": False,
    "execution_authorized": False,
    "live_execution": False,
    "financial_execution": False,
    "next_step_authorized": False,
    "automatic_execution_authorized": False,
    "order_submission_available": False,
}


def opportunity(
    *,
    match_id: str,
    status: str = "PROFITABLE",
    net_profit: float = 5.0,
) -> dict:
    return {
        "match_id": match_id,
        "left_key": f"left:{match_id}",
        "right_key": f"right:{match_id}",
        "status": status,
        "best_direction": {
            "net_profit": net_profit,
        },
        **SAFE_FLAGS,
    }


class EconomicEngineStub:
    def __init__(
        self,
        payload: dict,
    ) -> None:
        self.payload = payload
        self.calls: list[bool] = []

    async def evaluate_confirmed_matches(
        self,
        *,
        force_refresh: bool = False,
    ) -> dict:
        self.calls.append(
            force_refresh
        )

        return self.payload


class SimulatorStub:
    def __init__(
        self,
        *,
        statuses: dict[str, str] | None = None,
        errors: set[str] | None = None,
    ) -> None:
        self.statuses = statuses or {}
        self.errors = errors or set()
        self.calls: list[dict] = []

    async def simulate_evaluation(
        self,
        *,
        evaluation,
        force_refresh: bool = False,
        persist: bool = False,
    ) -> dict:
        match_id = evaluation["match_id"]

        self.calls.append(
            {
                "match_id": match_id,
                "force_refresh": force_refresh,
                "persist": persist,
            }
        )

        if match_id in self.errors:
            raise RuntimeError(
                f"simulation failure: {match_id}"
            )

        status = self.statuses.get(
            match_id,
            "SIMULATED",
        )

        return {
            "status": status,
            "record": {
                "match_id": match_id,
            },
            "persisted": persist,
            "audit": (
                {"sequence": 1}
                if persist
                else None
            ),
            **SAFE_FLAGS,
        }


class BlockingEconomicEngine:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def evaluate_confirmed_matches(
        self,
        *,
        force_refresh: bool = False,
    ) -> dict:
        self.started.set()

        await self.release.wait()

        return {
            "status": "NO_CONFIRMED_MATCHES",
            "confirmed_matches": 0,
            "opportunities": [],
            **SAFE_FLAGS,
        }


def test_status_is_safe_and_ready():
    runtime = ShadowExecutionRuntime(
        economic_engine=EconomicEngineStub(
            {
                "status": "NO_CONFIRMED_MATCHES",
                "confirmed_matches": 0,
                "opportunities": [],
                **SAFE_FLAGS,
            }
        ),
        simulator=SimulatorStub(),
    )

    payload = runtime.status()

    assert payload["status"] == "READY"
    assert payload["phase"] == "9F"
    assert payload["runtime_mode"] == (
        "SHADOW_SIMULATION_ONLY"
    )
    assert payload["scheduler_connected"] is False
    assert payload["paper_account_mutation"] is False
    assert payload["exchange_imports"] is False
    assert payload["oms_imports"] is False
    assert payload["wallet_access"] is False
    assert payload["credential_access"] is False
    assert payload["persistence_default"] is False

    for flag in PROTECTED_FALSE_FLAGS:
        assert payload[flag] is False


def test_persistence_default_cannot_be_enabled():
    try:
        ShadowExecutionRuntime(
            economic_engine=EconomicEngineStub({}),
            simulator=SimulatorStub(),
            persistence_default=True,
        )
    except ValueError as exc:
        assert "persist?ncia autom?tica" in str(
            exc
        )
    else:
        raise AssertionError(
            "Runtime aceitou persist?ncia "
            "autom?tica insegura."
        )


def test_cycle_without_confirmed_matches_is_safe():
    engine = EconomicEngineStub(
        {
            "status": "NO_CONFIRMED_MATCHES",
            "confirmed_matches": 0,
            "opportunities": [],
            **SAFE_FLAGS,
        }
    )
    simulator = SimulatorStub()

    runtime = ShadowExecutionRuntime(
        economic_engine=engine,
        simulator=simulator,
    )

    payload = asyncio.run(
        runtime.run_cycle()
    )

    assert payload["status"] == (
        "NO_CONFIRMED_MATCHES"
    )
    assert payload["confirmed_matches"] == 0
    assert payload["evaluated_opportunities"] == 0
    assert payload["selected_opportunities"] == 0
    assert payload["results"] == []
    assert simulator.calls == []
    assert runtime.status()[
        "completed_cycle_count"
    ] == 1


def test_only_profitable_opportunities_are_simulated():
    engine = EconomicEngineStub(
        {
            "status": "EVALUATED",
            "confirmed_matches": 3,
            "opportunities": [
                opportunity(
                    match_id="profitable",
                ),
                opportunity(
                    match_id="not-profitable",
                    status="NOT_PROFITABLE",
                    net_profit=-1,
                ),
                opportunity(
                    match_id="rejected",
                    status="REJECTED",
                    net_profit=0,
                ),
            ],
            **SAFE_FLAGS,
        }
    )
    simulator = SimulatorStub()

    runtime = ShadowExecutionRuntime(
        economic_engine=engine,
        simulator=simulator,
    )

    payload = asyncio.run(
        runtime.run_cycle()
    )

    assert payload["status"] == "COMPLETED"
    assert payload["evaluated_opportunities"] == 3
    assert payload["eligible_opportunities"] == 1
    assert payload["selected_opportunities"] == 1
    assert payload["simulated"] == 1
    assert [
        item["match_id"]
        for item in simulator.calls
    ] == ["profitable"]


def test_cycle_respects_maximum_opportunity_limit():
    opportunities = [
        opportunity(
            match_id=f"match-{index}",
            net_profit=10 - index,
        )
        for index in range(5)
    ]

    engine = EconomicEngineStub(
        {
            "status": "EVALUATED",
            "confirmed_matches": 5,
            "opportunities": opportunities,
            **SAFE_FLAGS,
        }
    )
    simulator = SimulatorStub()

    runtime = ShadowExecutionRuntime(
        economic_engine=engine,
        simulator=simulator,
        max_opportunities_per_cycle=2,
    )

    payload = asyncio.run(
        runtime.run_cycle()
    )

    assert payload["eligible_opportunities"] == 5
    assert payload["selected_opportunities"] == 2
    assert len(simulator.calls) == 2
    assert [
        item["match_id"]
        for item in simulator.calls
    ] == [
        "match-0",
        "match-1",
    ]


def test_force_refresh_and_persistence_are_forwarded_safely():
    engine = EconomicEngineStub(
        {
            "status": "EVALUATED",
            "confirmed_matches": 1,
            "opportunities": [
                opportunity(
                    match_id="match-1",
                )
            ],
            **SAFE_FLAGS,
        }
    )
    simulator = SimulatorStub()

    runtime = ShadowExecutionRuntime(
        economic_engine=engine,
        simulator=simulator,
    )

    payload = asyncio.run(
        runtime.run_cycle(
            force_refresh=True,
            persist=True,
        )
    )

    assert engine.calls == [True]
    assert simulator.calls == [
        {
            "match_id": "match-1",
            "force_refresh": False,
            "persist": True,
        }
    ]
    assert payload["persist_requested"] is True
    assert payload["results"][0][
        "persisted"
    ] is True


def test_simulation_failure_is_isolated_inside_cycle():
    engine = EconomicEngineStub(
        {
            "status": "EVALUATED",
            "confirmed_matches": 2,
            "opportunities": [
                opportunity(
                    match_id="good",
                ),
                opportunity(
                    match_id="bad",
                ),
            ],
            **SAFE_FLAGS,
        }
    )
    simulator = SimulatorStub(
        errors={"bad"},
    )

    runtime = ShadowExecutionRuntime(
        economic_engine=engine,
        simulator=simulator,
    )

    payload = asyncio.run(
        runtime.run_cycle()
    )

    assert payload["status"] == (
        "COMPLETED_WITH_ERRORS"
    )
    assert payload["simulated"] == 1
    assert payload["errors_count"] == 1
    assert payload["errors"][0][
        "match_id"
    ] == "bad"
    assert runtime.status()[
        "failed_cycle_count"
    ] == 0
    assert runtime.status()[
        "error_count"
    ] == 1


def test_unsafe_economic_payload_fails_closed():
    unsafe = {
        "status": "EVALUATED",
        "confirmed_matches": 1,
        "opportunities": [],
        **SAFE_FLAGS,
    }
    unsafe["live_execution"] = True

    runtime = ShadowExecutionRuntime(
        economic_engine=EconomicEngineStub(
            unsafe
        ),
        simulator=SimulatorStub(),
    )

    payload = asyncio.run(
        runtime.run_cycle()
    )

    assert payload["status"] == "FAILED"
    assert "flags inseguras" in payload["error"]
    assert runtime.status()[
        "failed_cycle_count"
    ] == 1

    for flag in PROTECTED_FALSE_FLAGS:
        assert payload[flag] is False


def test_overlapping_cycle_is_skipped():
    async def scenario():
        engine = BlockingEconomicEngine()

        runtime = ShadowExecutionRuntime(
            economic_engine=engine,
            simulator=SimulatorStub(),
        )

        first_task = asyncio.create_task(
            runtime.run_cycle()
        )

        await engine.started.wait()

        skipped = await runtime.run_cycle()

        engine.release.set()

        first = await first_task

        return runtime, first, skipped

    runtime, first, skipped = asyncio.run(
        scenario()
    )

    assert first["status"] == (
        "NO_CONFIRMED_MATCHES"
    )
    assert skipped["status"] == (
        "SKIPPED_ALREADY_RUNNING"
    )
    assert runtime.status()[
        "skipped_cycle_count"
    ] == 1
    assert runtime.status()["status"] == "READY"


def test_runtime_file_has_no_live_execution_imports():
    runtime_path = Path(
        "app/paper/"
        "shadow_execution_runtime.py"
    )

    source = runtime_path.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(source)

    forbidden_modules = (
        "app.exchanges",
        "app.orders",
        "app.oms",
        "app.trading",
    )

    imported_modules = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(
                alias.name
                for alias in node.names
            )

        elif isinstance(node, ast.ImportFrom):
            imported_modules.append(
                node.module or ""
            )

    violations = [
        module
        for module in imported_modules
        if any(
            module == forbidden
            or module.startswith(
                forbidden + "."
            )
            for forbidden in forbidden_modules
        )
    ]

    assert violations == []

    forbidden_identifiers = {
        "private_key",
        "wallet",
        "submit_order",
        "send_order",
    }

    identifiers = {
        node.id.lower()
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
    }

    identifiers.update(
        node.attr.lower()
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
    )

    assert (
        forbidden_identifiers
        & identifiers
    ) == set()


def test_router_exposes_only_read_only_endpoints():
    expected_paths = {
        "/real-markets/shadow-runtime/health",
        "/real-markets/shadow-runtime/status",
        "/real-markets/shadow-runtime/metrics",
        "/real-markets/shadow-runtime/last-cycle",
        "/real-markets/shadow-runtime/architecture",
    }

    routes = {
        route.path: set(
            route.methods or set()
        )
        for route in shadow_runtime_router.routes
    }

    assert set(routes) == expected_paths

    for methods in routes.values():
        assert methods == {"GET"}


def test_read_only_endpoint_payloads_are_safe():
    async def scenario():
        return [
            await shadow_runtime_health(),
            await shadow_runtime_status(),
            await shadow_runtime_metrics(),
            await shadow_runtime_architecture(),
        ]

    payloads = asyncio.run(
        scenario()
    )

    for payload in payloads:
        for flag in PROTECTED_FALSE_FLAGS:
            assert payload[flag] is False

        assert payload.get(
            "paper_account_mutation",
            False,
        ) is False

        assert payload.get(
            "wallet_access",
            False,
        ) is False

        assert payload.get(
            "credential_access",
            False,
        ) is False


def test_application_openapi_registers_phase9f_routes():
    app = create_app()

    schema = app.openapi()

    prefix = (
        "/real-markets/shadow-runtime"
    )

    paths = {
        path
        for path in schema["paths"]
        if path.startswith(prefix)
    }

    assert paths == {
        f"{prefix}/health",
        f"{prefix}/status",
        f"{prefix}/metrics",
        f"{prefix}/last-cycle",
        f"{prefix}/architecture",
    }


def test_phase9f_openapi_has_no_write_methods():
    app = create_app()

    schema = app.openapi()

    prefix = (
        "/real-markets/shadow-runtime"
    )

    for path, operations in (
        schema["paths"].items()
    ):
        if not path.startswith(prefix):
            continue

        assert set(
            operations
        ) == {"get"}

        assert "post" not in operations
        assert "put" not in operations
        assert "patch" not in operations
        assert "delete" not in operations


def test_shadow_runtime_scheduler_settings_are_fail_closed():
    from app.core.settings import Settings

    default = Settings(
        _env_file=None,
    )

    assert (
        default.SHADOW_RUNTIME_ENABLED
        is True
    )
    assert (
        default.SHADOW_RUNTIME_SCHEDULER_ENABLED
        is False
    )
    assert (
        default.SHADOW_RUNTIME_PERSIST_AUDIT
        is False
    )
    assert isinstance(
        default.SHADOW_RUNTIME_INTERVAL_SECONDS,
        int,
    )
    assert (
        default.SHADOW_RUNTIME_INTERVAL_SECONDS
        >= 10
    )
    assert (
        default
        .SHADOW_RUNTIME_MAX_OPPORTUNITIES_PER_CYCLE
        > 0
    )

    with pytest.raises(
        ValueError,
        match="SHADOW_RUNTIME_PERSIST_AUDIT",
    ):
        Settings(
            _env_file=None,
            SHADOW_RUNTIME_PERSIST_AUDIT=True,
        )

    with pytest.raises(
        ValueError,
        match="SHADOW_RUNTIME_ENABLED",
    ):
        Settings(
            _env_file=None,
            SHADOW_RUNTIME_ENABLED=False,
            SHADOW_RUNTIME_SCHEDULER_ENABLED=True,
        )

    with pytest.raises(
        ValueError,
        match="SCHEDULER_ENABLED",
    ):
        Settings(
            _env_file=None,
            SCHEDULER_ENABLED=False,
            SHADOW_RUNTIME_SCHEDULER_ENABLED=True,
        )

    with pytest.raises(
        ValueError,
        match="pelo menos 10 segundos",
    ):
        Settings(
            _env_file=None,
            SHADOW_RUNTIME_INTERVAL_SECONDS=9,
        )

    with pytest.raises(
        ValueError,
        match="deve ser positivo",
    ):
        Settings(
            _env_file=None,
            SHADOW_RUNTIME_MAX_OPPORTUNITIES_PER_CYCLE=0,
        )


def test_shadow_scheduler_cycle_stays_disabled_by_default(
    monkeypatch,
):
    import app.scheduler.tasks as scheduler_tasks

    monkeypatch.setattr(
        scheduler_tasks.settings,
        "SHADOW_RUNTIME_ENABLED",
        False,
    )

    async def forbidden_cycle(
        **kwargs,
    ):
        raise AssertionError(
            "O runtime nao deveria ser executado."
        )

    monkeypatch.setattr(
        scheduler_tasks.shadow_execution_runtime,
        "run_cycle",
        forbidden_cycle,
    )

    result = asyncio.run(
        scheduler_tasks
        .shadow_runtime_cycle_async()
    )

    assert result["status"] == "DISABLED"
    assert (
        result["persistence_requested"]
        is False
    )
    assert (
        result["paper_account_mutation"]
        is False
    )
    assert result["simulation_only"] is True

    protected_flags = (
        "paper_execution_authorized",
        "live_authorization",
        "execution_authorized",
        "live_execution",
        "financial_execution",
        "next_step_authorized",
        "automatic_execution_authorized",
        "order_submission_available",
    )

    for flag in protected_flags:
        assert result[flag] is False


def test_shadow_scheduler_cycle_forwards_safe_configuration(
    monkeypatch,
):
    import app.scheduler.tasks as scheduler_tasks

    monkeypatch.setattr(
        scheduler_tasks.settings,
        "SHADOW_RUNTIME_ENABLED",
        True,
    )
    monkeypatch.setattr(
        scheduler_tasks.settings,
        "SHADOW_RUNTIME_FORCE_REFRESH",
        True,
    )
    monkeypatch.setattr(
        scheduler_tasks.settings,
        "SHADOW_RUNTIME_PERSIST_AUDIT",
        False,
    )
    monkeypatch.setattr(
        scheduler_tasks.settings,
        "SHADOW_RUNTIME_MAX_OPPORTUNITIES_PER_CYCLE",
        3,
    )

    captured = {}

    async def fake_run_cycle(
        **kwargs,
    ):
        captured.update(
            kwargs
        )

        return {
            "status": "COMPLETED",
            "test_result": True,
        }

    monkeypatch.setattr(
        scheduler_tasks.shadow_execution_runtime,
        "run_cycle",
        fake_run_cycle,
    )

    result = asyncio.run(
        scheduler_tasks
        .shadow_runtime_cycle_async()
    )

    assert captured == {
        "force_refresh": True,
        "persist": False,
        "max_opportunities": 3,
    }

    assert result == {
        "status": "COMPLETED",
        "test_result": True,
    }


def test_shadow_runtime_sync_task_delegates_to_async_cycle(
    monkeypatch,
):
    import app.scheduler.tasks as scheduler_tasks

    expected = {
        "status": "NO_CONFIRMED_MATCHES",
        "simulated": 0,
        "rejected": 0,
        "errors_count": 0,
    }

    calls = []

    async def fake_cycle():
        calls.append(
            "executed"
        )

        return dict(
            expected
        )

    monkeypatch.setattr(
        scheduler_tasks,
        "shadow_runtime_cycle_async",
        fake_cycle,
    )

    result = (
        scheduler_tasks.shadow_runtime_task()
    )

    assert calls == [
        "executed",
    ]
    assert result == expected
