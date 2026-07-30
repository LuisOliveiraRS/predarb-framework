import importlib
from pathlib import Path
from types import SimpleNamespace


def test_portfolio_uses_paper_account(monkeypatch):
    module = importlib.import_module(
        "app.dashboard.dashboard_service"
    )
    paper_module = importlib.import_module(
        "app.paper.paper_runtime"
    )

    class FakeAccount:
        def snapshot(self, include_trades=False):
            assert include_trades is False

            return {
                "equity": 10_000.0,
                "wallet": {
                    "balance": 10_000.0,
                    "cash": 9_700.0,
                    "available": 9_700.0,
                    "locked": 300.0,
                },
            }

    runtime = SimpleNamespace(
        enabled=True,
        account=FakeAccount(),
    )

    monkeypatch.setattr(
        paper_module,
        "paper_account_runtime",
        runtime,
    )

    portfolio = module._default_portfolio()

    assert portfolio["total"] == 10_000.0
    assert portfolio["available"] == 9_700.0
    assert portfolio["locked"] == 300.0
    assert portfolio["utilization"] == 0.03
    assert portfolio["source"] == "paper_account"


def test_builder_extracts_total_from_portfolio():
    module = importlib.import_module(
        "app.dashboard.builder"
    )

    builder_class = next(
        value
        for value in vars(module).values()
        if isinstance(value, type)
        and value.__module__ == module.__name__
        and callable(getattr(value, "build", None))
    )

    snapshot = builder_class().build(
        {
            "markets": [],
            "opportunities": [],
            "orders": [],
            "positions": [],
            "connections": [],
            "portfolio": {
                "total": 10_000.0,
                "available": 10_000.0,
                "locked": 0.0,
            },
            "pnl": 0.0,
            "ai_confidence": 0.0,
            "events": [],
        }
    )

    assert snapshot["portfolio"]["total"] == 10_000.0
    assert snapshot["portfolio"]["available"] == 10_000.0
    assert snapshot["portfolio"]["locked"] == 0.0

    portfolio_card = next(
        card
        for card in snapshot["cards"]
        if "portfolio" in {
            str(value).strip().lower()
            for value in card.values()
        }
    )

    numeric_values = {
        float(value)
        for value in portfolio_card.values()
        if isinstance(value, (int, float))
        and not isinstance(value, bool)
    }

    assert 10_000.0 in numeric_values


def test_paper_values_are_not_ellipsized():
    backend_dir = Path(__file__).resolve().parents[1]

    css = (
        backend_dir
        / "app"
        / "dashboard"
        / "static"
        / "css"
        / "dashboard.css"
    ).read_text(encoding="utf-8")

    start = css.index(".paper-metric strong {")
    end = css.index("}", start)
    block = css[start:end]

    assert "text-overflow: clip" in block
    assert "overflow: visible" in block
    assert "text-overflow: ellipsis" not in block
