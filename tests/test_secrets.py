import pytest

from common.secrets import EnvironmentSecretStore


def test_environment_secret_store_reads_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_SECRET", "present")
    assert EnvironmentSecretStore().get("TEST_SECRET") == "present"


def test_environment_secret_store_rejects_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TEST_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="TEST_SECRET"):
        EnvironmentSecretStore().get("TEST_SECRET")

