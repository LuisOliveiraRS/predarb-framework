from pathlib import Path

import pytest

from app.orders.order import Order
from app.paper import PaperAccount, PaperAccountRepository
from app.pipeline.pipeline import Pipeline
from app.pipeline.pipeline_context import PipelineContext
from app.pipeline.stages.paper_account_stage import PaperAccountStage
from app.pipeline.stages.paper_stage import PaperStage


def orders(prefix: str):
    return [
        Order(
            id=f"{prefix}-yes",
            platform="A",
            market="event",
            symbol="event",
            side="BUY",
            quantity=100,
            price=0.44,
            opportunity_id=prefix,
            leg="YES",
            mode="PAPER",
        ),
        Order(
            id=f"{prefix}-no",
            platform="B",
            market="event",
            symbol="event",
            side="BUY",
            quantity=100,
            price=0.46,
            opportunity_id=prefix,
            leg="NO",
            mode="PAPER",
        ),
    ]


def execute(account: PaperAccount, values):
    pipeline = Pipeline(
        [
            PaperStage(fee_rate=0.001, strict=True),
            PaperAccountStage(account=account, persist=False),
        ]
    )
    return pipeline.execute(PipelineContext({"orders": values}))


def test_paper_account_commit_and_mark_to_market():
    account = PaperAccount(initial_balance=10_000, auto_persist=False)
    result = execute(account, orders("commit"))
    assert result.success
    snapshot = account.snapshot()
    assert snapshot["trade_count"] == 2
    assert snapshot["open_positions"] == 2
    assert snapshot["wallet"]["balance"] == 9909.91
    account.mark_to_market(
        {position.id: 0.5 for position in account.positions.open_positions()}
    )
    assert account.snapshot()["unrealized_pnl"] == 9.91


def test_paper_account_settlement_realizes_profit():
    account = PaperAccount(initial_balance=10_000, auto_persist=False)
    execute(account, orders("settle"))
    for position in account.positions.open_positions():
        account.settle(position.id, 1.0 if position.leg == "YES" else 0.0)
    snapshot = account.snapshot()
    assert snapshot["open_positions"] == 0
    assert snapshot["closed_positions"] == 2
    assert snapshot["realized_pnl"] == 9.91
    assert snapshot["equity"] == 10009.91


def test_paper_account_json_round_trip(tmp_path: Path):
    repository = PaperAccountRepository(tmp_path / "account.json")
    account = PaperAccount(
        initial_balance=10_000,
        repository=repository,
        auto_persist=False,
    )
    execute(account, orders("persist"))
    account.save()
    restored = PaperAccount(
        initial_balance=1,
        repository=repository,
        auto_persist=False,
    )
    assert restored.load()
    assert restored.snapshot()["trade_count"] == 2
    assert restored.snapshot()["wallet"]["balance"] == 9909.91


def test_paper_account_rejects_duplicate_and_insufficient_balance():
    account = PaperAccount(initial_balance=10_000, auto_persist=False)
    values = orders("duplicate")
    result = execute(account, values)
    before = account.snapshot()
    with pytest.raises(ValueError, match="já processadas"):
        account.commit_execution(values, result.context.execution_reports, persist=False)
    assert account.snapshot() == before

    poor = PaperAccount(initial_balance=10, auto_persist=False)
    context = PipelineContext({"orders": orders("poor")})
    PaperStage(fee_rate=0.001, strict=True).process(context)
    poor_before = poor.snapshot()
    with pytest.raises(ValueError, match="Saldo paper insuficiente"):
        poor.commit_execution(context.orders, context.execution_reports, persist=False)
    assert poor.snapshot() == poor_before
