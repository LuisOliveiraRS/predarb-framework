from __future__ import annotations

import inspect
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.ai.runtime import ai_runtime
from app.api.routers.arbitrage import router as arbitrage_router
from app.api.routers.connectors import router as connectors_router
from app.api.routers.markets import router as markets_router
from app.api.routers.opportunities import router as opportunities_router
from app.api.routers.paper import router as paper_router
from app.api.routers.paper_performance_monitor import router as paper_performance_monitor_router
from app.api.routers.paper_performance_incidents import router as paper_performance_incidents_router
from app.api.routers.paper_performance_incident_runtime import router as paper_performance_incident_runtime_router
from app.api.routers.paper_operations_center import router as paper_operations_center_router
from app.api.routers.paper_readiness import router as paper_readiness_router
from app.api.routers.paper_readiness_history import router as paper_readiness_history_router
from app.api.routers.paper_readiness_runtime import router as paper_readiness_runtime_router
from app.api.routers.paper_stability_certification import router as paper_stability_certification_router
from app.api.routers.paper_certification_evidence import router as paper_certification_evidence_router
from app.api.routers.paper_certification_evidence_monitor import router as paper_certification_evidence_monitor_router
from app.api.routers.paper_certification_evidence_incidents import router as paper_certification_evidence_incidents_router
from app.api.routers.paper_certification_evidence_incident_runtime import router as paper_certification_evidence_incident_runtime_router
from app.api.routers.paper_certification_assurance import router as paper_certification_assurance_router
from app.api.routers.paper_certification_assurance_history import router as paper_certification_assurance_history_router
from app.api.routers.paper_certification_assurance_history_runtime import router as paper_certification_assurance_history_runtime_router
from app.api.routers.paper_certification_assurance_history_runtime_dashboard import router as paper_certification_assurance_history_runtime_dashboard_router
from app.api.routers.paper_certification_assurance_gate import router as paper_certification_assurance_gate_router
from app.api.routers.paper_certification_assurance_gate_history import router as paper_certification_assurance_gate_history_router
from app.api.routers.paper_certification_assurance_gate_history_runtime import router as paper_certification_assurance_gate_history_runtime_router
from app.api.routers.paper_certification_assurance_gate_history_runtime_dashboard import router as paper_certification_assurance_gate_history_runtime_dashboard_router
from app.api.routers.paper_final_validation import router as paper_final_validation_router
from app.api.routers.paper_final_validation_history import router as paper_final_validation_history_router
from app.api.routers.paper_final_validation_history_runtime import router as paper_final_validation_history_runtime_router
from app.api.routers.paper_final_validation_history_runtime_dashboard import router as paper_final_validation_history_runtime_dashboard_router
from app.api.routers.paper_final_validation_evidence import router as paper_final_validation_evidence_router
from app.api.routers.paper_final_validation_evidence_monitor import router as paper_final_validation_evidence_monitor_router
from app.api.routers.paper_final_validation_evidence_incidents import router as paper_final_validation_evidence_incidents_router
from app.api.routers.paper_final_validation_evidence_incidents_dashboard import router as paper_final_validation_evidence_incidents_dashboard_router
from app.api.routers.paper_final_validation_evidence_incident_runtime import router as paper_final_validation_evidence_incident_runtime_router
from app.api.routers.paper_final_validation_evidence_incident_runtime_dashboard import router as paper_final_validation_evidence_incident_runtime_dashboard_router
from app.api.routers.paper_final_operational_assurance import router as paper_final_operational_assurance_router
from app.api.routers.paper_final_operational_assurance_history import router as paper_final_operational_assurance_history_router
from app.api.routers.paper_final_assurance_history_runtime import router as paper_final_assurance_history_runtime_router
from app.api.routers.paper_final_assurance_history_runtime_dashboard import router as paper_final_assurance_history_runtime_dashboard_router
from app.api.routers.paper_final_assurance_qualification_gate import router as paper_final_assurance_qualification_gate_router
from app.api.routers.paper_final_assurance_qualification_gate_history import router as paper_final_assurance_qualification_gate_history_router
from app.api.routers.paper_final_assurance_qualification_gate_history_runtime import router as paper_final_assurance_qualification_gate_history_runtime_router
from app.api.routers.paper_final_assurance_qualification_gate_history_runtime_dashboard import router as paper_final_assurance_qualification_gate_history_runtime_dashboard_router
from app.api.routers.paper_final_assurance_qualification_certification import router as paper_final_assurance_qualification_certification_router
from app.api.routers.paper_final_qualification_certification_history import router as paper_final_qualification_certification_history_router
from app.api.routers.real_market_data import router as real_market_data_router
from app.api.routers.polymarket_read_only import router as polymarket_read_only_router
from app.api.routers.market_matching import router as market_matching_router
from app.api.routers.economic_opportunities import router as economic_opportunities_router
from app.api.routers.real_opportunity_radar import router as real_opportunity_radar_router
from app.api.routers.shadow_execution import router as shadow_execution_router
from app.api.routers.shadow_execution_runtime import router as shadow_execution_runtime_router
from app.api.routers.paper_certification_evidence_incident_runtime_dashboard import router as paper_certification_evidence_incident_runtime_dashboard_router
from app.api.routers.paper_certification_evidence_incident_dashboard import router as paper_certification_evidence_incident_dashboard_router
from app.api.routers.paper_readiness_runtime_dashboard import router as paper_readiness_runtime_dashboard_router
from app.api.routers.paper_performance_incident_runtime_dashboard import router as paper_performance_incident_runtime_dashboard_router
from app.api.routers.paper_performance_incident_dashboard import router as paper_performance_incident_dashboard_router
from app.api.routers.paper_performance import router as paper_performance_router
from app.api.routers.paper_performance_dashboard import router as paper_performance_dashboard_router
from app.api.routers.plugins import router as plugins_router
from app.api.routers.signals import router as signals_router
from app.api.routers.statistics import router as statistics_router
from app.connectors.hyperliquid.connector import HyperliquidConnector
from app.connectors.manager.connector_manager import connector_manager
from app.connectors.mock.connector import MockConnector
from app.auth.router import router as auth_router
from app.auth.password_recovery import router as password_recovery_router
from app.auth.mfa_router import router as mfa_router
from app.core.settings import settings
from app.dashboard.api import router as dashboard_api_router
from app.dashboard.event_listener import dashboard_event_listener
from app.dashboard.router import router as dashboard_page_router
from app.dashboard.router_api import router as ai_dashboard_api_router
from app.dashboard.router_service import router_service
from app.dashboard.router_ws import router as ai_dashboard_ws_router
from app.database.init_database import initialize_database
from app.events.event_bus import event_bus
from app.orders.execution_worker import execution_worker
from app.plugins.manager import plugin_manager
from app.paper.paper_runtime import paper_account_runtime
from app.paper.paper_session_runtime import paper_session_runtime
from app.realtime.ws_router import router as websocket_router
from app.paper.shadow_execution_runtime import (
    shadow_execution_runtime,
)
from app.scheduler.scheduler import scheduler_service
from app.scheduler.tasks import (
    market_update_task,
    shadow_runtime_task,
    update_markets_async,
)
from app.services.market_listener import market_listener
from app.strategies.strategy_manager import strategy_manager


logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DASHBOARD_STATIC_DIR = BASE_DIR / "dashboard" / "static"
MANAGED_CONNECTORS = ("mock", "hyperliquid")


async def _call_optional_method(target: Any, method_name: str, **kwargs: Any) -> Any:
    method = getattr(target, method_name, None)
    if not callable(method):
        return None

    result = method(**kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


def _configure_connectors() -> list[str]:
    """Registra somente os conectores habilitados no ambiente."""

    for name in MANAGED_CONNECTORS:
        if connector_manager.exists(name):
            connector_manager.unregister(name)

    if settings.MOCK_CONNECTOR_ENABLED:
        connector_manager.register("mock", MockConnector())

    if settings.HYPERLIQUID_CONNECTOR_ENABLED:
        connector_manager.register("hyperliquid", HyperliquidConnector())

    return connector_manager.names()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida oficial, idempotente e configurável da aplicação."""

    logger.info("Inicializando PredArb Framework.")

    app.state.startup_completed = False
    app.state.startup_error = None
    app.state.connector_startup = {}
    app.state.initial_market_count = 0
    app.state.ai_startup = ai_runtime.status(resolve_engine=False)
    app.state.lifecycle = {
        "database": False,
        "plugins": False,
        "kernel": False,
        "ai": False,
        "connectors": False,
        "market_listener": False,
        "scheduler": False,
        "shadow_runtime_scheduler": False,
        "execution_worker": False,
        "router_dashboard": False,
        "paper_account": False,
        "paper_session": False,
    }

    try:
        initialize_database()
        app.state.lifecycle["database"] = True

        plugin_manager.load()
        app.state.lifecycle["plugins"] = True

        from app.kernel.kernel_bootstrap import kernel_bootstrap

        kernel_bootstrap.start()
        app.state.lifecycle["kernel"] = True

        app.state.ai_startup = ai_runtime.startup()
        app.state.lifecycle["ai"] = True

        paper_account_runtime.startup()
        app.state.lifecycle["paper_account"] = bool(
            paper_account_runtime.enabled
        )
        paper_session_runtime.startup()
        app.state.lifecycle["paper_session"] = bool(
            paper_session_runtime.enabled
        )

        connector_names = _configure_connectors()
        app.state.connector_startup = await connector_manager.connect_all()
        app.state.lifecycle["connectors"] = bool(connector_names)

        event_bus.subscribe(
            "OpportunityFound",
            dashboard_event_listener.opportunity_found,
        )

        strategy_manager.initialize()

        market_listener.start()
        app.state.lifecycle["market_listener"] = True

        if settings.INITIAL_MARKET_SYNC_ENABLED:
            initial_markets = await update_markets_async()
            app.state.initial_market_count = len(initial_markets)

        shadow_execution_runtime.set_scheduler_connected(
            False
        )
        app.state.lifecycle[
            "shadow_runtime_scheduler"
        ] = False

        if settings.SCHEDULER_ENABLED:
            scheduler_service.add_job(
                market_update_task,
                seconds=settings.MARKET_UPDATE_INTERVAL_SECONDS,
                job_id="market_update_task",
                replace_existing=True,
            )

            if (
                settings.SHADOW_RUNTIME_ENABLED
                and settings.SHADOW_RUNTIME_SCHEDULER_ENABLED
            ):
                scheduler_service.add_job(
                    shadow_runtime_task,
                    seconds=(
                        settings
                        .SHADOW_RUNTIME_INTERVAL_SECONDS
                    ),
                    job_id="shadow_runtime_task",
                    replace_existing=True,
                )

                shadow_execution_runtime.set_scheduler_connected(
                    True
                )

                app.state.lifecycle[
                    "shadow_runtime_scheduler"
                ] = True

            scheduler_service.start()
            app.state.lifecycle["scheduler"] = True

        if settings.EXECUTION_WORKER_ENABLED:
            await _call_optional_method(execution_worker, "start")
            app.state.lifecycle["execution_worker"] = True

        if settings.ROUTER_DASHBOARD_ENABLED:
            await _call_optional_method(router_service, "start")
            app.state.lifecycle["router_dashboard"] = True

        app.state.startup_completed = True
        logger.info("PredArb Framework pronto para operar.")
        yield

    except Exception as exc:
        app.state.startup_error = str(exc)
        logger.exception("Falha durante o startup do PredArb Framework.")
        raise

    finally:
        app.state.startup_completed = False
        logger.info("Finalizando PredArb Framework.")

        shadow_execution_runtime.set_scheduler_connected(
            False
        )
        app.state.lifecycle[
            "shadow_runtime_scheduler"
        ] = False

        cleanup_steps = (
            (router_service, "stop", "Router Dashboard IA"),
            (execution_worker, "stop", "Execution Worker"),
            (scheduler_service, "shutdown", "Scheduler"),
            (market_listener, "stop", "Market Listener"),
        )

        for target, method_name, label in cleanup_steps:
            try:
                await _call_optional_method(target, method_name)
            except Exception:
                logger.exception("Erro ao encerrar %s.", label)

        try:
            await connector_manager.disconnect_all()
        except Exception:
            logger.exception("Erro ao desconectar Connectors.")

        try:
            await paper_session_runtime.stop()
        except Exception:
            logger.exception("Erro ao encerrar a sessão Paper.")

        try:
            paper_account_runtime.shutdown()
        except Exception:
            logger.exception("Erro ao persistir a conta Paper.")

        try:
            ai_runtime.shutdown()
        except Exception:
            logger.exception("Erro ao encerrar AI Runtime.")

        try:
            from app.kernel.kernel_bootstrap import kernel_bootstrap

            await _call_optional_method(kernel_bootstrap, "stop")
        except Exception:
            logger.exception("Erro ao encerrar Kernel.")

        try:
            plugin_manager.stop()
        except Exception:
            logger.exception("Erro ao encerrar Plugins.")

        logger.info("PredArb Framework finalizado.")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        description="Framework Open Plugin para Mercados Preditivos",
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    if settings.PUBLIC_CORS_ENABLED:
        allowed_origins = [
            origin
            for origin in (
                settings
                .PUBLIC_CORS_ALLOWED_ORIGINS
                .split(",")
            )
            if origin
        ]

        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=False,
            allow_methods=[
                "GET",
                "POST",
                "OPTIONS",
            ],
            allow_headers=[
                "Authorization",
                "Content-Type",
            ],
        )


    app.state.startup_completed = False
    app.state.startup_error = None
    app.state.connector_startup = {}
    app.state.initial_market_count = 0
    app.state.ai_startup = ai_runtime.status(resolve_engine=False)
    app.state.lifecycle = {}

    app.mount(
        "/dashboard/static",
        StaticFiles(directory=str(DASHBOARD_STATIC_DIR)),
        name="dashboard_static",
    )

    @app.get("/")
    async def root():
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "running",
            "dashboard": "/dashboard",
            "documentation": "/docs",
            "ai": {
                "enabled": settings.AI_ENABLED,
                "advisory_only": True,
                "execution_authorized": False,
                "auto_load_model": False,
            },
        }

    def _health_status() -> str:
        startup_completed = bool(
            getattr(app.state, "startup_completed", False)
        )
        startup_error = getattr(
            app.state,
            "startup_error",
            None,
        )

        if startup_error:
            return "degraded"
        if startup_completed:
            return "healthy"
        return "starting"

    def _health_details() -> dict[str, Any]:
        return {
            "status": _health_status(),
            "version": settings.APP_VERSION,
            "startup_error": getattr(
                app.state,
                "startup_error",
                None,
            ),
            "lifecycle": dict(
                getattr(app.state, "lifecycle", {}) or {}
            ),
            "initial_markets": int(
                getattr(
                    app.state,
                    "initial_market_count",
                    0,
                )
                or 0
            ),
            "connectors": connector_manager.statuses(),
            "connector_configuration": {
                "mock_enabled": settings.MOCK_CONNECTOR_ENABLED,
                "hyperliquid_enabled": (
                    settings.HYPERLIQUID_CONNECTOR_ENABLED
                ),
                "initial_sync_enabled": (
                    settings.INITIAL_MARKET_SYNC_ENABLED
                ),
            },
            "scheduler": {
                "enabled": settings.SCHEDULER_ENABLED,
                **scheduler_service.status(),
            },
            "plugins": plugin_manager.status(),
            "events": event_bus.status(),
            "dashboard": {
                "page": "/dashboard",
                "api": "/dashboard/api/snapshot",
                "router_ws": "/ws/router",
            },
            "ai": ai_runtime.status(resolve_engine=False),
            "paper": paper_account_runtime.status(),
            "paper_session": paper_session_runtime.status(),
        }

    @app.get("/health", include_in_schema=False)
    async def health():
        return {
            "status": _health_status(),
            "version": settings.APP_VERSION,
        }

    if settings.DEBUG:
        @app.get(
            "/internal/health",
            include_in_schema=False,
        )
        async def internal_health():
            return _health_details()

    @app.get("/version")
    async def version():
        return {"version": settings.APP_VERSION}

    for router in (
        plugins_router,
        markets_router,
        arbitrage_router,
        signals_router,
        statistics_router,
        opportunities_router,
        connectors_router,
        paper_router,
        paper_performance_monitor_router,
        paper_performance_incidents_router,
        paper_performance_incident_runtime_router,
        paper_operations_center_router,
        paper_readiness_router,
        paper_readiness_history_router,
        paper_readiness_runtime_router,
        paper_stability_certification_router,
        paper_certification_evidence_router,
        paper_certification_evidence_monitor_router,
        paper_certification_evidence_incidents_router,
        paper_certification_evidence_incident_runtime_router,
        paper_certification_assurance_router,
        paper_certification_assurance_history_router,
        paper_certification_assurance_history_runtime_router,
        paper_certification_assurance_gate_router,
        paper_certification_assurance_gate_history_router,
        paper_certification_assurance_gate_history_runtime_router,
        paper_final_validation_router,
        paper_final_validation_history_router,
        paper_final_validation_history_runtime_router,
        paper_final_validation_evidence_router,
        paper_final_validation_evidence_monitor_router,
        paper_final_validation_evidence_incidents_router,
        paper_final_validation_evidence_incident_runtime_router,
        paper_final_operational_assurance_router,
        paper_final_operational_assurance_history_router,
        paper_final_assurance_history_runtime_router,
        paper_final_assurance_qualification_gate_router,
        paper_final_assurance_qualification_gate_history_router,
        paper_final_assurance_qualification_gate_history_runtime_router,
        paper_final_assurance_qualification_gate_history_runtime_dashboard_router,
        paper_final_assurance_qualification_certification_router,
        paper_final_qualification_certification_history_router,
        real_market_data_router,
        polymarket_read_only_router,
        market_matching_router,
        economic_opportunities_router,
        real_opportunity_radar_router,
        shadow_execution_router,
        shadow_execution_runtime_router,
        paper_final_assurance_history_runtime_dashboard_router,
        paper_final_validation_evidence_incident_runtime_dashboard_router,
        paper_final_validation_evidence_incidents_dashboard_router,
        paper_final_validation_history_runtime_dashboard_router,
        paper_certification_assurance_gate_history_runtime_dashboard_router,
        paper_certification_assurance_history_runtime_dashboard_router,
        paper_certification_evidence_incident_runtime_dashboard_router,
        paper_certification_evidence_incident_dashboard_router,
        paper_readiness_runtime_dashboard_router,
        paper_performance_incident_runtime_dashboard_router,
        paper_performance_incident_dashboard_router,
        paper_performance_router,
        paper_performance_dashboard_router,
        websocket_router,
        auth_router,
        password_recovery_router,
        mfa_router,
        dashboard_page_router,
        dashboard_api_router,
        ai_dashboard_api_router,
        ai_dashboard_ws_router,
    ):
        app.include_router(router)

    return app
