from __future__ import annotations

from pathlib import Path

from app.dashboard.cache import DashboardCache
from app.dashboard.dashboard_service import DashboardService, DashboardSources
from app.dashboard.dashboard_state import DashboardState
from app.dashboard.router import templates
from app.paper.paper_account import PaperAccount
from app.paper.paper_equity_tracker import PaperEquityTracker
from app.paper.paper_position_manager import PaperPositionManager
from app.paper.paper_repository import PaperAccountRepository
from app.paper.paper_trade_history import PaperTradeHistory
from app.paper.paper_wallet import PaperWallet


def build_account(path: Path) -> PaperAccount:
    return PaperAccount(
        initial_balance=10_000,
        wallet=PaperWallet(10_000),
        history=PaperTradeHistory(),
        positions=PaperPositionManager(),
        equity_tracker=PaperEquityTracker(max_points=100),
        repository=PaperAccountRepository(path),
        auto_persist=False,
    )


def commit_sample(account: PaperAccount) -> None:
    order = {
        "id": "paper-order-1",
        "opportunity_id": "opp-1",
        "platform": "mock",
        "symbol": "BTC-PAPER",
        "market": "BTC paper test",
        "leg": "YES",
        "side": "BUY",
        "quantity": 100,
        "price": 0.40,
    }
    report = {
        "order_id": "paper-order-1",
        "status": "FILLED",
        "mode": "PAPER",
        "platform": "mock",
        "symbol": "BTC-PAPER",
        "leg": "YES",
        "side": "BUY",
        "filled_quantity": 100,
        "average_price": 0.40,
        "gross_notional": 40,
        "fee": 0.04,
    }
    account.commit_execution([order], [report], persist=False)


def test_equity_curve_records_and_persists(tmp_path):
    path = tmp_path / "paper-account.json"
    account = build_account(path)

    commit_sample(account)
    position = account.positions.open_positions()[0]
    account.mark_to_market({position.id: 0.55})
    account.save()

    snapshot = account.snapshot()
    assert len(snapshot["equity_curve"]) >= 3
    assert snapshot["equity_curve"][-1]["reason"] == "MARK_TO_MARKET"
    assert snapshot["equity_analytics"]["points"] == len(snapshot["equity_curve"])
    assert snapshot["equity_analytics"]["current_equity"] == snapshot["equity"]

    restored = build_account(path)
    assert restored.load() is True
    restored_snapshot = restored.snapshot()
    assert restored_snapshot["equity_curve"] == snapshot["equity_curve"]
    assert restored_snapshot["equity_analytics"] == snapshot["equity_analytics"]


def test_version_one_state_is_migrated(tmp_path):
    account = build_account(tmp_path / "paper-account.json")
    legacy_state = account.export_state()
    legacy_state["state_version"] = 1
    legacy_state.pop("equity_curve", None)

    migrated = build_account(tmp_path / "migrated.json")
    migrated.restore_state(legacy_state)

    snapshot = migrated.snapshot()
    assert len(snapshot["equity_curve"]) == 1
    assert snapshot["equity_curve"][0]["reason"] == "RESTORE"
    assert snapshot["execution_authorized"] is False
    assert snapshot["live_execution"] is False


def test_dashboard_snapshot_includes_paper_account(tmp_path):
    account = build_account(tmp_path / "paper-account.json")
    commit_sample(account)
    paper_snapshot = account.snapshot()

    service = DashboardService(
        state=DashboardState(),
        cache=DashboardCache(),
        sources=DashboardSources(
            markets=lambda: [],
            orders=lambda: [],
            positions=lambda: [],
            trades=lambda: [],
            portfolio=lambda: {},
            statistics=lambda: {},
            router=lambda: {},
            paper=lambda: {**paper_snapshot, "enabled": True},
            notifications=lambda: [],
        ),
    )

    snapshot = service.snapshot()
    paper = snapshot["data"]["paper"]
    assert paper["mode"] == "PAPER"
    assert paper["trade_count"] == 1
    assert paper["open_positions"] == 1
    assert paper["equity_curve"]
    assert snapshot["diagnostics"]["sources"]["paper_positions"] == 1
    assert snapshot["diagnostics"]["sources"]["paper_trades"] == 1


def test_dashboard_template_has_paper_components():
    template = templates.get_template("dashboard.html")
    html = template.render(
        title="PredArb Enterprise Dashboard",
        api_base="/dashboard/api",
        router_ws_path="/ws/router",
    )

    for identifier in (
        'id="paper-panel"',
        'id="paper-metrics"',
        'id="paper-equity-chart"',
        'id="paper-positions-body"',
        'id="paper-trades-body"',
    ):
        assert identifier in html
