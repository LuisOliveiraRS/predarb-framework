from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Mapping

from app.orders.order import Order


class OrderSerializer:
    """Serializa e restaura ordens em estruturas compatíveis com JSON."""

    @classmethod
    def _serialize_value(cls, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value

        if isinstance(value, Enum):
            return cls._serialize_value(value.value)

        if isinstance(value, (datetime, date)):
            return value.isoformat()

        if isinstance(value, Mapping):
            return {
                str(key): cls._serialize_value(item)
                for key, item in value.items()
            }

        if isinstance(value, (list, tuple, set, frozenset)):
            return [cls._serialize_value(item) for item in value]

        to_dict = getattr(value, "to_dict", None)
        if callable(to_dict):
            return cls._serialize_value(to_dict())

        if is_dataclass(value):
            return cls._serialize_value(asdict(value))

        return str(value)

    def serialize(self, order: Any) -> dict[str, Any]:
        if order is None:
            raise ValueError("order não pode ser None.")

        if isinstance(order, Mapping):
            data = dict(order)
        else:
            to_dict = getattr(order, "to_dict", None)
            if callable(to_dict):
                data = to_dict()
            elif is_dataclass(order):
                data = asdict(order)
            else:
                raise TypeError("order deve ser Order, Mapping ou dataclass.")

        serialized = self._serialize_value(data)
        if not isinstance(serialized, dict):
            raise TypeError("A serialização da ordem deve resultar em um dicionário.")
        return serialized

    to_dict = serialize

    def serialize_many(self, orders: Any) -> list[dict[str, Any]]:
        if isinstance(orders, (str, bytes, Mapping)):
            raise TypeError("orders deve ser uma coleção de ordens.")
        return [self.serialize(order) for order in orders]

    def deserialize(self, data: Mapping[str, Any]) -> Order:
        if not isinstance(data, Mapping):
            raise TypeError("data deve ser um Mapping.")
        return Order.from_dict(data)

    from_dict = deserialize

    def deserialize_many(self, values: Any) -> list[Order]:
        if isinstance(values, (str, bytes, Mapping)):
            raise TypeError("values deve ser uma coleção de dicionários.")
        return [self.deserialize(value) for value in values]


order_serializer = OrderSerializer()
