import os
from abc import ABC, abstractmethod


class SecretStore(ABC):
    """Boundary for secret retrieval; implementations must never log values."""

    @abstractmethod
    def get(self, name: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def exists(self, name: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def put(self, name: str, value: str) -> None:
        raise NotImplementedError


class EnvironmentSecretStore(SecretStore):
    """Bootstrap SecretStore backed by container environment variables."""

    def get(self, name: str) -> str:
        value = os.getenv(name)
        if not value:
            raise RuntimeError(f"Required secret is not configured: {name}")
        return value

    def exists(self, name: str) -> bool:
        return bool(os.getenv(name))

    def put(self, name: str, value: str) -> None:
        raise NotImplementedError("Bootstrap environment secrets are immutable")
