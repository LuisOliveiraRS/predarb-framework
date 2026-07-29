from app.events.event import Event
from app.events.event_bus import EventBus


def test_event_bus_isolated_and_idempotent():
    bus = EventBus()
    received = []

    def handler(event):
        received.append(event)

    assert bus.subscribe("market.updated", handler) is True
    assert bus.subscribe("market.updated", handler) is False

    event = Event(name="market.updated", payload={"price": 0.62})
    results = bus.publish(event)

    assert len(results) == 1
    assert received == [event]
    assert received[0].payload["price"] == 0.62
    assert bus.status()["listeners"] == 1

    assert bus.unsubscribe("market.updated", handler) is True
    assert bus.unsubscribe("market.updated", handler) is False
    assert bus.publish(event) == []
