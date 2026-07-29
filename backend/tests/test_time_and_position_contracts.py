from datetime import timezone

from app.commands.base_command import BaseCommand
from app.domain.order import Order
from app.events.base_event import BaseEvent
from app.positions.position import Position
from app.positions.position_closer import position_closer
from app.positions.position_status import PositionStatus


def test_dataclass_timestamps_are_fresh_and_timezone_aware():
    first = BaseCommand(name="first")
    second = BaseCommand(name="second")
    event = BaseEvent(name="event")
    order = Order(
        platform="mock",
        question="Q",
        side="YES",
        price=0.4,
        quantity=1,
    )

    assert first.created_at is not second.created_at
    assert first.created_at.tzinfo is timezone.utc
    assert second.created_at.tzinfo is timezone.utc
    assert event.created_at.tzinfo is timezone.utc
    assert order.created_at.tzinfo is timezone.utc


def test_position_contract_is_consolidated_and_compatible():
    position = Position(
        platform="mock",
        question="Q",
        side="ARBITRAGE",
        quantity=1,
        average_price=0.45,
        orders=[{"id": "o-1"}],
        metadata={"source": "test"},
    )

    assert position.status is PositionStatus.OPEN
    assert position.closed is False
    assert position.orders[0]["id"] == "o-1"
    assert position.metadata["source"] == "test"

    position_closer.close(position)

    assert position.status is PositionStatus.CLOSED
    assert position.closed is True
    assert position.closed_at is not None
    assert position.closed_at.tzinfo is timezone.utc
