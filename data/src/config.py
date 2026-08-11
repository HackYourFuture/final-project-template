"""Configuration read from environment variables.

Every setting comes from the environment. Nothing is hard-coded and no secret
is ever committed, which is the same rule you followed from Week 2 onwards.
Copy .env.example to .env for local development. In Azure the values come from
Key Vault, and in Databricks from your team's secret scope.

This file is finished. You should not need to change much here beyond adding
settings your own source needs.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


class MissingSetting(RuntimeError):
    """Raised when a required environment variable is not set."""


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise MissingSetting(
            f"{name} is not set. Copy .env.example to .env and fill it in."
        )
    return value


@dataclass(frozen=True)
class Config:
    """Settings the ingestion job needs.

    Notice what is absent: there is no client id, no secret, no connection
    string. The job authenticates as itself, through the managed identity
    Azure gives the container, so the only settings here are names.

    `databricks_catalog` is used for one log line telling you where dbt will
    see the file. It is optional for that reason.
    """

    source_api_url: str
    source_name: str
    storage_account: str
    databricks_catalog: str


def load_config() -> Config:
    """Build a Config, failing loudly when something is missing.

    Failing at startup is deliberate. A job that runs for ten minutes and then
    dies on a missing password wastes ten minutes.
    """
    return Config(
        source_api_url=_required("SOURCE_API_URL"),
        source_name=os.getenv("SOURCE_NAME", "source"),
        storage_account=_required("STORAGE_ACCOUNT"),
        databricks_catalog=os.getenv("DATABRICKS_CATALOG", "<your catalog>"),
    )
