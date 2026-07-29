from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from app.paper.paper_risk import PaperRiskGuard, paper_risk_guard
from app.pipeline.pipeline_stage import PipelineStage


class PaperRiskStage(PipelineStage):
    """Filtro final de risco da conta Paper, executado antes de OrderStage."""

    def __init__(
        self,
        *,
        guard: PaperRiskGuard | None = None,
        enabled: bool = True,
        strict: bool = False,
    ) -> None:
        self.guard = guard or paper_risk_guard
        self.enabled = bool(enabled)
        self.strict = bool(strict)

    @staticmethod
    def _attach(opportunity: Any, decision: Mapping[str, Any]) -> Any:
        result = deepcopy(opportunity)
        if isinstance(result, dict):
            result["paper_risk"] = dict(decision)
            return result
        metadata = getattr(result, "metadata", None)
        if isinstance(metadata, dict):
            metadata["paper_risk"] = dict(decision)
        return result

    def process(self, context: Any) -> Any:
        opportunities = list(context.opportunities or [])
        if not self.enabled:
            context.metadata["paper_risk"] = {
                "status": "DISABLED",
                "input": len(opportunities),
                "approved": len(opportunities),
                "rejected": 0,
                "execution_authorized": False,
                "live_execution": False,
            }
            return context

        approved: list[Any] = []
        rejected: list[dict[str, Any]] = []
        for index, opportunity in enumerate(opportunities):
            try:
                decision = self.guard.evaluate(opportunity).to_dict()
            except Exception as exc:
                if self.strict:
                    raise
                decision = {
                    "approved": False,
                    "stopped": False,
                    "codes": ["RISK_EVALUATION_ERROR"],
                    "reasons": [str(exc)],
                    "metrics": {},
                    "limits": self.guard.limits.to_dict(),
                    "mode": "PAPER",
                    "execution_authorized": False,
                    "live_execution": False,
                }

            decorated = self._attach(opportunity, decision)
            if decision["approved"]:
                approved.append(decorated)
            else:
                rejected.append(
                    {
                        "index": index,
                        "codes": list(decision.get("codes", [])),
                        "reasons": list(decision.get("reasons", [])),
                        "stopped": bool(decision.get("stopped", False)),
                    }
                )

        context.opportunities = approved
        context.metadata["paper_risk"] = {
            "status": "APPROVED" if approved else "REJECTED" if opportunities else "EMPTY",
            "input": len(opportunities),
            "approved": len(approved),
            "rejected": len(rejected),
            "rejections": rejected,
            "session": self.guard.session_status().to_dict(),
            "execution_authorized": False,
            "live_execution": False,
        }
        return context

    execute = process
