from abc import ABC
from abc import abstractmethod


class BaseRepository(ABC):

    @abstractmethod
    def all(self):
        pass

    @abstractmethod
    def save(self, item):
        pass

    @abstractmethod
    def delete(self, item):
        pass