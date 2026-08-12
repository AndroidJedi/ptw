import os
from pathlib import Path

import psycopg

from common.secrets import EnvironmentSecretStore, SecretStore


def database_url(store: SecretStore | None = None) -> str:
    secrets = store or EnvironmentSecretStore()
    return (
        f"postgresql://{os.getenv('POSTGRES_USER', 'ptw')}:"
        f"{secrets.get('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST', 'postgres')}:"
        f"{os.getenv('POSTGRES_PORT', '5432')}/{os.getenv('POSTGRES_DB', 'ptw')}"
    )


def apply_migrations(directory: str = "/app/migrations") -> None:
    migration_dir = Path(directory)
    if not migration_dir.is_dir():
        raise RuntimeError(f"Migration directory not found: {migration_dir}")
    with psycopg.connect(database_url()) as connection:
        connection.execute("SELECT pg_advisory_lock(781045221)")
        try:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(name TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
            )
            applied = {
                row[0]
                for row in connection.execute("SELECT name FROM schema_migrations").fetchall()
            }
            for path in sorted(migration_dir.glob("*.sql")):
                if path.name in applied:
                    continue
                connection.execute(path.read_text(encoding="utf-8"))
                connection.execute(
                    "INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,)
                )
                connection.commit()
        finally:
            if connection.info.transaction_status != 0:
                connection.rollback()
            connection.execute("SELECT pg_advisory_unlock(781045221)")
