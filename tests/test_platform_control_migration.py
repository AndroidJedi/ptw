from pathlib import Path


def test_platform_control_migration_is_singleton_and_seeded() -> None:
    migration = Path("migrations/011_platform_control.sql").read_text()
    assert "singleton BOOLEAN PRIMARY KEY" in migration
    assert "CHECK (singleton)" in migration
    assert "emergency_stop BOOLEAN NOT NULL DEFAULT FALSE" in migration
    assert "ON CONFLICT(singleton) DO NOTHING" in migration
