from __future__ import annotations

from typing import Any

from app.paper.paper_account import PaperAccount, paper_account
from app.pipeline.pipeline_stage import PipelineStage


class PaperAccountStage(PipelineStage):
    """Confirma explicitamente fills paper na conta virtual persistente."""

    def __init__(
        self,
        *,
        account: PaperAccount | None = None,
        persist: bool = True,
        enabled: bool = True,
    ) -> None:
        self.account = account or paper_account
        self.persist = bool(persist)
        self.enabled = bool(enabled)

    def process(self, context: Any) -> Any:
        if not self.enabled:
            context.metadata["paper_account"] = {
                "status": "DISABLED",
                "execution_authorized": False,
            }
            return context

        reports = list(context.execution_reports or [])
        orders = list(context.orders or [])
        if not reports:
            context.metadata["paper_account"] = {
                "status": "EMPTY",
                "execution_authorized": False,
            }
            return context

        result = self.account.commit_execution(
            orders,
            reports,
            persist=self.persist,
        )
        context.metadata["paper_account"] = {
            "status": result["status"],
            "orders_committed": result["orders_committed"],
            "execution_id": result["execution_id"],
            "execution_authorized": False,
            "live_execution": False,
        }
        context.positions = self.account.positions.snapshot(include_closed=False)
        return context

    execute = process
