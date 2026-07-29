from enum import Enum


class PositionStatus(str, Enum):

    OPEN = "OPEN"

    MONITORING = "MONITORING"

    PARTIAL_EXIT = "PARTIAL_EXIT"

    CLOSED = "CLOSED"

    CANCELLED = "CANCELLED"