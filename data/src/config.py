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

    The client secret is not a field here. It is fetched from Key Vault at
    run time by the identity of whatever is running: your `az login` locally,
    the Container Apps job's managed identity in Azure.
    """

    source_api_url: str
    source_name: str
    databricks_host: str
    databricks_catalog: str


def load_config() -> Config:
    """Build a Config, failing loudly when something is missing.

    Failing at startup is deliberate. A job that runs for ten minutes and then
    dies on a missing password wastes ten minutes.
    """
    return Config(
        source_api_url=_required("SOURCE_API_URL"),
        source_name=os.getenv("SOURCE_NAME", "source"),
        databricks_host=_required("DATABRICKS_HOST").replace("https://", ""),
        databricks_catalog=_required("DATABRICKS_CATALOG"),
    )
