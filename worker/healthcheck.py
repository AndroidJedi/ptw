import os

import psycopg

from common.secrets import EnvironmentSecretStore

secrets = EnvironmentSecretStore()
url = (
    f"postgresql://{os.getenv('POSTGRES_USER', 'ptw')}:{secrets.get('POSTGRES_PASSWORD')}@"
    f"{os.getenv('POSTGRES_HOST', 'postgres')}:{os.getenv('POSTGRES_PORT', '5432')}/"
    f"{os.getenv('POSTGRES_DB', 'ptw')}"
)
with psycopg.connect(url, connect_timeout=3) as connection:
    connection.execute("SELECT 1")

