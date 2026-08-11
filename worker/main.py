import logging
import os
import signal
import time

import psycopg

from common.secrets import EnvironmentSecretStore

logging.basicConfig(
    level=os.getenv("PTW_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("ptw.worker")
running = True
secrets = EnvironmentSecretStore()


def stop(_signum: int, _frame: object) -> None:
    global running
    running = False


def database_url() -> str:
    return (
        f"postgresql://{os.getenv('POSTGRES_USER', 'ptw')}:"
        f"{secrets.get('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST', 'postgres')}:"
        f"{os.getenv('POSTGRES_PORT', '5432')}/{os.getenv('POSTGRES_DB', 'ptw')}"
    )


def main() -> None:
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    poll_seconds = max(2, int(os.getenv("WORKER_POLL_SECONDS", "10")))
    logger.info("Commander worker started")
    while running:
        try:
            with psycopg.connect(database_url(), connect_timeout=3) as connection:
                connection.execute("SELECT 1")
        except Exception as exc:
            logger.warning("Worker database probe failed: %s", type(exc).__name__)
        time.sleep(poll_seconds)
    logger.info("Commander worker stopped")


if __name__ == "__main__":
    main()

