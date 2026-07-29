from dataclasses import dataclass


@dataclass
class Exchange:

    name: str

    enabled: bool = True

    connected: bool = False

    latency: float = 0

    fee: float = 0