"""API pública consolidada do OMS do PredArb Framework.

O pacote expõe classes, enums e contratos estáveis. Instâncias singleton como
``order_manager`` e ``order_builder`` permanecem nos respectivos módulos:

    from app.orders.order_manager import order_manager
    from app.orders.order_builder import order_builder

Essa separação evita colisões entre atributos do pacote e submódulos Python
com o mesmo nome, além de impedir inicialização prematura de conectores,
workers ou serviços de execução.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


_EXPORTS: dict[str, tuple[str, str]] = {
    # Modelos e enums
    "Order": ("app.orders.order", "Order"),
    "OrderSide": ("app.orders.order_side", "OrderSide"),
    "OrderType": ("app.orders.order_type", "OrderType"),
    "OrderStatus": ("app.orders.order_status", "OrderStatus"),
    "TimeInForce": ("app.orders.time_in_force", "TimeInForce"),
    "OrderEvent": ("app.orders.order_event", "OrderEvent"),
    "ExecutionPolicy": ("app.orders.execution_policy", "ExecutionPolicy"),
    "Fill": ("app.orders.fill", "Fill"),

    # Construção e validação
    "OrderBuilder": ("app.orders.order_builder", "OrderBuilder"),
    "OrderValidator": ("app.orders.order_validator", "OrderValidator"),
    "OrderManager": ("app.orders.order_manager", "OrderManager"),

    # Estado, persistência e observabilidade
    "OrderBatch": ("app.orders.order_batch", "OrderBatch"),
    "OrderRepository": ("app.orders.order_repository", "OrderRepository"),
    "OrderQueue": ("app.orders.order_queue", "OrderQueue"),
    "OrderHistory": ("app.orders.order_history", "OrderHistory"),
    "OrderTracker": ("app.orders.order_tracker", "OrderTracker"),
    "OrderSerializer": ("app.orders.order_serializer", "OrderSerializer"),
    "OrderMetrics": ("app.orders.order_metrics", "OrderMetrics"),
    "OrderStatistics": ("app.orders.order_statistics", "OrderStatistics"),
    "OrderTransitionError": (
        "app.orders.order_state_machine",
        "OrderTransitionError",
    ),
    "OrderStateMachine": (
        "app.orders.order_state_machine",
        "OrderStateMachine",
    ),
    "OrderLifecycle": ("app.orders.order_lifecycle", "OrderLifecycle"),

    # Roteamento, despacho e resultados
    "OrderResponse": ("app.orders.order_response", "OrderResponse"),
    "OrderRouter": ("app.orders.order_router", "OrderRouter"),
    "OrderDispatcher": ("app.orders.order_dispatcher", "OrderDispatcher"),
    "OrderSender": ("app.orders.order_sender", "OrderSender"),
    "OrderExecutor": ("app.orders.order_executor", "OrderExecutor"),
    "OrderExecutionReport": (
        "app.orders.order_execution_report",
        "OrderExecutionReport",
    ),
    "OrderResult": ("app.orders.order_result", "OrderResult"),

    # Fills
    "FillEngine": ("app.orders.fill_engine", "FillEngine"),
    "FillService": ("app.orders.fill_service", "FillService"),
    "FillReport": ("app.orders.fill_report", "FillReport"),
    "FillRepository": ("app.orders.fill_repository", "FillRepository"),
    "MatchingEngine": ("app.orders.matching_engine", "MatchingEngine"),

    # Execução em lote e agregação
    "OrderBatchExecutor": (
        "app.orders.order_batch_executor",
        "OrderBatchExecutor",
    ),
    "OrderBatchReport": (
        "app.orders.order_batch_report",
        "OrderBatchReport",
    ),
    "MultiExchangeExecutor": (
        "app.orders.multi_exchange_executor",
        "MultiExchangeExecutor",
    ),
    "ExecutionAggregator": (
        "app.orders.execution_aggregator",
        "ExecutionAggregator",
    ),
    "ExecutionReport": ("app.orders.execution_report", "ExecutionReport"),
    "ExecutionStatistics": (
        "app.orders.execution_statistics",
        "ExecutionStatistics",
    ),
    "ExecutionLogger": ("app.orders.execution_logger", "ExecutionLogger"),

    # Estratégias de planejamento
    "ExecutionStrategy": (
        "app.orders.execution_strategy",
        "ExecutionStrategy",
    ),
    "ExecutionStrategyContext": (
        "app.orders.execution_strategy",
        "ExecutionStrategyContext",
    ),
    "ExecutionStrategyPlan": (
        "app.orders.execution_strategy",
        "ExecutionStrategyPlan",
    ),
    "allocate_quantities": (
        "app.orders.execution_strategy",
        "allocate_quantities",
    ),
    "ExecutionStrategyFactory": (
        "app.orders.execution_strategy_factory",
        "ExecutionStrategyFactory",
    ),
    "MarketStrategy": ("app.orders.strategies", "MarketStrategy"),
    "LimitStrategy": ("app.orders.strategies", "LimitStrategy"),
    "SplitStrategy": ("app.orders.strategies", "SplitStrategy"),
    "TWAPStrategy": ("app.orders.strategies", "TWAPStrategy"),
    "VWAPStrategy": ("app.orders.strategies", "VWAPStrategy"),
    "IcebergStrategy": ("app.orders.strategies", "IcebergStrategy"),
    "ParallelStrategy": ("app.orders.strategies", "ParallelStrategy"),

    # Smart e Adaptive Routing
    "SmartRoutePlan": ("app.orders.smart_order_router", "SmartRoutePlan"),
    "SmartOrderRouter": (
        "app.orders.smart_order_router",
        "SmartOrderRouter",
    ),
    "SmartOrderExecution": (
        "app.orders.smart_order_execution",
        "SmartOrderExecution",
    ),
    "SmartExecutionResult": (
        "app.orders.smart_execution_engine",
        "SmartExecutionResult",
    ),
    "SmartExecutionEngine": (
        "app.orders.smart_execution_engine",
        "SmartExecutionEngine",
    ),

    # Fila, worker, retry e agendamento
    "ExecutionQueueClosed": (
        "app.orders.execution_queue",
        "ExecutionQueueClosed",
    ),
    "ExecutionQueue": ("app.orders.execution_queue", "ExecutionQueue"),
    "ExecutionTask": ("app.orders.execution_worker", "ExecutionTask"),
    "ExecutionWorker": ("app.orders.execution_worker", "ExecutionWorker"),
    "RetryResult": ("app.orders.retry_engine", "RetryResult"),
    "RetryEngine": ("app.orders.retry_engine", "RetryEngine"),
    "ScheduledOrder": ("app.orders.order_scheduler", "ScheduledOrder"),
    "OrderScheduler": ("app.orders.order_scheduler", "OrderScheduler"),
}


__all__ = tuple(_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attribute_name = target
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
