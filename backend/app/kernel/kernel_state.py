from enum import Enum


class KernelState(Enum):

    CREATED = "CREATED"

    INITIALIZING = "INITIALIZING"

    RUNNING = "RUNNING"

    PAUSED = "PAUSED"

    STOPPED = "STOPPED"

    ERROR = "ERROR"