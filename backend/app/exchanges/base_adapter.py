from abc import ABC
from abc import abstractmethod


class BaseExchangeAdapter(ABC):
    """
    Contrato base para qualquer Exchange.
    """

    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def disconnect(self):
        pass

    @abstractmethod
    def place_order(self, order):
        pass

    @abstractmethod
    def cancel_order(self, order):
        pass

    @abstractmethod
    def get_order(self, order_id):
        pass

    @abstractmethod
    def get_balance(self):
        pass

    @abstractmethod
    def get_positions(self):
        pass

    @abstractmethod
    def ping(self):
        pass

    @abstractmethod
    def health(self):
        pass