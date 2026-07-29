from dataclasses import asdict


class PositionSerializer:

    def serialize(self, position):

        data = asdict(position)

        data["status"] = position.status.value

        data["created_at"] = position.created_at.isoformat()

        if position.closed_at:

            data["closed_at"] = position.closed_at.isoformat()

        return data


position_serializer = PositionSerializer()