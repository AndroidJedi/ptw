import logging
import os

import psycopg
from fastapi import FastAPI, HTTPException

from common.secrets import EnvironmentSecretStore

logging.basicConfig(
    level=os.getenv("PTW_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("ptw.commander")
secrets = EnvironmentSecretStore()

app = FastAPI(title="PTW Commander", version="0.1.0", docs_url=None, redoc_url=None)


def database_url() -> str:
    return (
        f"postgresql://{os.getenv('POSTGRES_USER', 'ptw')}:"
        f"{secrets.get('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST', 'postgres')}:"
        f"{os.getenv('POSTGRES_PORT', '5432')}/{os.getenv('POSTGRES_DB', 'ptw')}"
    )


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok", "service": "commander-api"}


@app.get("/health/ready")
def ready() -> dict[str, str]:
    try:
        with psycopg.connect(database_url(), connect_timeout=3) as connection:
            connection.execute("SELECT 1")
    except Exception as exc:
        logger.warning("Database readiness check failed: %s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ready"}

