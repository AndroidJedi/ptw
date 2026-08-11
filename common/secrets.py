import os
from abc import ABC, abstractmethod


class SecretStore(ABC):
    """Boundary for secret retrieval; implementations must never log values."""

    @abstractmethod
    def get(self, name: str) -> str:
        raise NotImplementedError


class EnvironmentSecretStore(SecretStore):
    """Bootstrap SecretStore backed by container environment variables."""

    def get(self, name: str) -> str:
        value = os.getenv(name)
        if not value:
            raise RuntimeError(f"Required secret is not configured: {name}")
        return value

