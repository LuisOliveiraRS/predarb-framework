"""Compatibilidade para o antigo ``app.dashboard.service``.

A implementação oficial vive em ``dashboard_service.py``.
"""

from app.dashboard.dashboard_service import (
    DashboardService,
    DashboardSources,
    dashboard_service,
)

__all__ = [
    "DashboardService",
    "DashboardSources",
    "dashboard_service",
]
