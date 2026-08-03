"""Configuration read from environment variables.

Every setting comes from the environment. Nothing is hard-coded and no
secret is ever committed, which is the same rule you followed from Week 2
onwards. Copy .env.example to .env for local development.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    source_api_url: str
    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str
    raw_schema: str

    @property
    def postgres_dsn(self) -> str:
        return (
            f"host={self.postgres_host} port={self.postgres_port} "
            f"dbname={self.postgres_db} user={self.postgres_user} "
            f"password={self.postgres_password}"
        )


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def load_config() -> Config:
    """Build a Config, failing loudly when something is missing.

    Failing at startup is deliberate. A pipeline that starts with half its
    configuration and dies twenty minutes later is far harder to debug.
    """
    return Config(
        source_api_url=_required("SOURCE_API_URL"),
        postgres_host=_required("POSTGRES_HOST"),
        postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
        postgres_db=_required("POSTGRES_DB"),
        postgres_user=_required("POSTGRES_USER"),
        postgres_password=_required("POSTGRES_PASSWORD"),
        raw_schema=os.getenv("POSTGRES_SCHEMA_RAW", "raw"),
    )
