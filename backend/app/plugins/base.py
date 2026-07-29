from abc import ABC, abstractmethod


class BasePlugin(ABC):

    name = "unknown"
    version = "0.0.1"


    @abstractmethod
    def start(self):
        pass


    @abstractmethod
    def stop(self):
        pass


    def health(self):

        return {
            "name": self.name,
            "version": self.version,
            "status": "healthy"
        }