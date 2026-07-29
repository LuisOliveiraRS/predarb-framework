from abc import ABC
from abc import abstractmethod


class BaseStrategy(ABC):
    """
    Interface base para todas as estratégias.
    """

    @property
    @abstractmethod
    def name(self):
        pass

    @abstractmethod
    def enabled(self):
        pass

    @abstractmethod
    def analyze(self, opportunities):
        pass