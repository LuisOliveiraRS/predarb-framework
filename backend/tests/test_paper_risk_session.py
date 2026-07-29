from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.market.comparators.cross_platform import CrossPlatformComparator
from app.paper.paper_account import PaperAccount
from app.paper.paper_equity_tracker import PaperEquityTracker
from app.paper.paper_position_manager import PaperPositionManager
from app.paper.paper_repository import PaperAccountRepository
from app.paper.paper_risk import PaperRiskGuard, PaperRiskLimits
from app.paper.paper_session import PaperSessionManager, PaperSessionRepository
from app.paper.paper_session_runtime import PaperSessionRuntime
from app.paper.paper_trade_history import PaperTradeHistory
from app.paper.paper_wallet import PaperWallet
from app.pipeline.pipeline_context import PipelineContext
from app.pipeline.stages.paper_risk_stage import PaperRiskStage


def build_account(path: Path, balance: float = 10_000.0) -> PaperAccount:
    return PaperAccount(
        initial_balance=balance,
        wallet=PaperWallet(balance),
        history=PaperTradeHistory(),
        positions=PaperPositionManager(),
        equity_tracker=PaperEquityTracker(max_points=100),
        repository=PaperAccountRepository(path),
        auto_persist=False,
    )


def opportunities() -> list[dict]:
    markets = [
        {
            "platform": "A",
            "question": "Will phase seven pass?",
            "yes": 0.40,
            "no": 0.60,
            "liquidity": 10_000,
            "volume": 10_000,
            "market_id": "phase7-a",
        },
        {
            "platform": "B",
            "question": "Will phase seven pass?",
            "yes": 0.55,
            "no": 0.45,
            "liquidity": 10_000,
            "volume": 10_000,
            "market_id": "phase7-b",
        },
    ]
    values = CrossPlatformComparator().compare(markets)
    assert values
    return values


def guard(account: PaperAccount, **overrides) -> PaperRiskGuard:
    defaults = {
        "max_trade_notional": 500,
        "max_total_exposure": 2_000,
        "max_market_exposure": 1_000,
        "max_open_positions": 10,
        "max_daily_trades": 20,
        "daily_loss_limit": 500,
        "max_drawdown_rate": 0.20,
        "min_roi": 0,
        "min_confidence": 0,
        "max_risk_score": 100,
    }
    defaults.update(overrides)
    return PaperRiskGuard(account=account, limits=PaperRiskLimits(**defaults))


def analyzed_opportunity(total: float = 250.0) -> dict:
    return {
        "question": "Will phase seven pass?",
        "market_id": "phase7-a:YES|phase7-b:NO",
        "buy_yes_platform": "A",
        "buy_no_platform": "B",
        "yes_price": 0.40,
        "no_price": 0.45,
        "roi": 17.64,
        "confidence": 0.95,
        "risk": {"score": 20},
        "stake": {
            "total": total,
            "yes": total * 0.40 / 0.85,
            "no": total * 0.45 / 0.85,
        },
        "approved": True,
    }


def test_paper_risk_approves_safe_and_rejects_limits(tmp_path):
    account = build_account(tmp_path / "account.json")
    safe = guard(account)
    decision = safe.evaluate(analyzed_opportunity())
    assert decision.approved is True
    assert decision.codes == []
    assert decision.metrics["projected_total_exposure"] == 250

    strict = guard(
        account,
        max_trade_notional=100,
        min_roi=20,
        min_confidence=0.99,
        max_risk_score=10,
    )
    rejected = strict.evaluate(analyzed_opportunity())
    assert rejected.approved is False
    assert {
        "TRADE_NOTIONAL_LIMIT",
        "ROI_BELOW_MINIMUM",
        "CONFIDENCE_BELOW_MINIMUM",
        "RISK_SCORE_ABOVE_MAXIMUM",
    }.issubset(set(rejected.codes))
    assert rejected.to_dict()["execution_authorized"] is False


def test_paper_risk_stage_filters_before_orders(tmp_path):
    account = build_account(tmp_path / "account.json")
    stage = PaperRiskStage(
        guard=guard(account, max_trade_notional=200),
        strict=True,
    )
    context = PipelineContext(
        {
            "opportunities": [
                analyzed_opportunity(total=100),
                analyzed_opportunity(total=300),
            ]
        }
    )
    stage.process(context)
    assert len(context.opportunities) == 1
    assert context.opportunities[0]["paper_risk"]["approved"] is True
    metadata = context.metadata["paper_risk"]
    assert metadata["approved"] == 1
    assert metadata["rejected"] == 1
    assert metadata["rejections"][0]["codes"] == ["TRADE_NOTIONAL_LIMIT"]


def test_paper_session_executes_and_persists_report(tmp_path):
    account = build_account(tmp_path / "account.json")
    manager = PaperSessionManager(
        account=account,
        risk_guard=guard(account),
        opportunity_source=opportunities,
        repository=PaperSessionRepository(tmp_path / "session.json"),
        stake_amount=250,
        max_opportunities_per_cycle=1,
        paper_fee_rate=0.001,
    )
    cycle = manager.run_cycle()
    assert cycle["status"] == "SUCCESS"
    assert cycle["orders"] == 2
    assert cycle["fills"] == 2
    assert account.snapshot()["trade_count"] == 2
    assert (tmp_path / "session.json").is_file()
    report = manager.report()
    assert report["total_cycles"] == 1
    assert report["successful_cycles"] == 1
    assert report["execution_authorized"] is False
    assert report["live_execution"] is False


def test_daily_stop_and_runtime_confirmation(tmp_path):
    account = build_account(tmp_path / "account.json")
    manager = PaperSessionManager(
        account=account,
        risk_guard=guard(account, daily_loss_limit=0.10),
        opportunity_source=opportunities,
        repository=PaperSessionRepository(tmp_path / "session.json"),
        stake_amount=250,
        max_opportunities_per_cycle=1,
        paper_fee_rate=0.001,
    )
    first = manager.run_cycle()
    assert first["status"] == "SUCCESS"
    # As fees Paper geram uma perda inicial superior a R$ 0,10.
    stopped = manager.run_cycle()
    assert stopped["status"] == "RISK_STOPPED"
    assert "DAILY_LOSS_LIMIT" in stopped["risk"]["codes"]

    runtime = PaperSessionRuntime(manager=manager, enabled=True, interval_seconds=1)

    async def scenario():
        with pytest.raises(ValueError, match="Confirmação inválida"):
            await runtime.start(confirm="NO")
        status = await runtime.start(confirm=runtime.START_CONFIRMATION)
        assert status["running"] is True
        await asyncio.sleep(0.05)
        stopped_status = await runtime.stop()
        assert stopped_status["running"] is False
        assert stopped_status["execution_authorized"] is False

    asyncio.run(scenario())


def test_paper_session_routes_are_registered():
    from fastapi.routing import APIRoute, iter_route_contexts

    from app.core.application import create_app

    app = create_app()

    paths = {
        context.path
        for context in iter_route_contexts(app.routes)
        if isinstance(context.original_route, APIRoute)
    }

    for path in (
        "/paper/risk/status",
        "/paper/session/status",
        "/paper/session/report",
        "/paper/session/cycle",
        "/paper/session/start",
        "/paper/session/stop",
        "/paper/session/reset-report",
    ):
        assert path in paths



def test_settings_reject_paper_session_auto_start():
    from app.core.settings import Settings

    with pytest.raises(Exception, match="PAPER_SESSION_AUTO_START"):
        Settings(_env_file=None, PAPER_SESSION_AUTO_START=True)
