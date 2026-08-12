"""Run SQL against the Databricks SQL warehouse over HTTP.

Used by the steps dbt cannot express: the enrichment job and the publish step.
See the README, "Talking to the warehouse", for why the token comes from Entra
rather than from the workspace.
"""

import json
import logging
import os
import time
import urllib.parse
import urllib.request
from typing import Protocol

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# The application id of Azure Databricks itself. Not a secret, not per team.
DATABRICKS_RESOURCE = "2ff814a6-3304-4ab8-85cb-cd0e6f879c1d"

# Longest the API may block before answering "still running". 50s is its max.
WAIT_TIMEOUT = "50s"

REQUIRED = (
    "DATABRICKS_HOST",
    "DATABRICKS_HTTP_PATH",
    "DATABRICKS_CATALOG",
)


class WarehouseError(RuntimeError):
    """A statement did not succeed."""


class Queryable(Protocol):
    """What the steps downstream need: two methods and a catalog name.

    Depending on this rather than on the class below is what lets the tests
    pass in a fake that records statements instead of sending them.
    """

    catalog: str

    def run(self, statement: str) -> list[list]: ...

    def query(self, statement: str) -> tuple[list[tuple[str, str]], list[list]]: ...


def warehouse_id(http_path: str) -> str:
    """The id out of the path dbt already needs, so there is one setting."""
    identifier = http_path.rstrip("/").rsplit("/", 1)[-1]
    if not identifier:
        raise ValueError(f"cannot read a warehouse id out of {http_path!r}")
    return identifier


def your_own_token() -> str:
    """A Databricks token for whoever is signed in.

    Your `az login` on your machine, the job's managed identity in Azure. No
    secret either way, and the warehouse logs the query against the identity
    that ran it rather than against a credential the whole team shares.
    """
    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential().get_token(f"{DATABRICKS_RESOURCE}/.default").token


def entra_token(
    tenant_id: str, client_id: str, client_secret: str, opener=urllib.request.urlopen
) -> str:
    """Exchange the team service principal for a Databricks access token.

    This is how the scheduled run authenticates. Locally you should not need
    it: see `your_own_token`.
    """
    body = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": f"{DATABRICKS_RESOURCE}/.default",
        }
    ).encode()
    request = urllib.request.Request(
        f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return json.load(opener(request, timeout=30))["access_token"]


class Warehouse:
    """One authenticated connection's worth of settings.

    `opener` exists so tests can pass a fake instead of urlopen.
    """

    def __init__(
        self,
        host: str,
        http_path: str,
        catalog: str,
        token: str,
        opener=urllib.request.urlopen,
        poll_seconds: float = 2.0,
    ) -> None:
        self.host = host.replace("https://", "").rstrip("/")
        self.warehouse_id = warehouse_id(http_path)
        self.catalog = catalog
        self.token = token
        self._opener = opener
        self._poll_seconds = poll_seconds

    @classmethod
    def from_env(cls, opener=urllib.request.urlopen) -> "Warehouse":
        """Build from the same variables dbt reads. Loads .env if present."""
        load_dotenv()
        missing = [name for name in REQUIRED if not os.getenv(name)]
        if missing:
            raise WarehouseError(
                "missing settings: " + ", ".join(missing) + ". "
                "These are the same values dbt uses, and none of them is a secret."
            )
        # The team's service principal when it is configured, which is how the
        # scheduled run authenticates. Otherwise you, which is how your own
        # runs should: nothing to copy out of Key Vault and onto your laptop.
        client_id = os.getenv("DATABRICKS_CLIENT_ID")
        client_secret = os.getenv("DATABRICKS_CLIENT_SECRET")
        if client_id and client_secret:
            tenant_id = os.getenv("AZURE_TENANT_ID")
            if not tenant_id:
                raise WarehouseError(
                    "DATABRICKS_CLIENT_ID is set but AZURE_TENANT_ID is not. An empty "
                    "tenant builds a token URL with nothing in the middle, and the only "
                    "symptom is a 404 that mentions neither."
                )
            token = entra_token(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
                opener=opener,
            )
        else:
            token = your_own_token()
        return cls(
            host=os.environ["DATABRICKS_HOST"],
            http_path=os.environ["DATABRICKS_HTTP_PATH"],
            catalog=os.environ["DATABRICKS_CATALOG"],
            token=token,
            opener=opener,
        )

    def _call(self, method: str, path: str, payload: dict | None = None) -> dict:
        request = urllib.request.Request(
            f"https://{self.host}{path}",
            data=json.dumps(payload).encode() if payload else None,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
        )
        return json.load(self._opener(request, timeout=300))

    def run(self, statement: str) -> list[list]:
        """Run one statement and return its rows, as lists of strings."""
        return self.query(statement)[1]

    def query(self, statement: str) -> tuple[list[tuple[str, str]], list[list]]:
        """Run one statement and return (columns, rows), waiting for it.

        Returning before the statement finished is the bug this avoids: the
        next step would build on a table that is still being written.
        """
        body = self._call(
            "POST",
            "/api/2.0/sql/statements",
            {
                "statement": statement,
                "warehouse_id": self.warehouse_id,
                "catalog": self.catalog,
                "wait_timeout": WAIT_TIMEOUT,
            },
        )
        while body.get("status", {}).get("state") in ("PENDING", "RUNNING"):
            time.sleep(self._poll_seconds)
            body = self._call("GET", f"/api/2.0/sql/statements/{body['statement_id']}")

        state = body.get("status", {}).get("state")
        if state != "SUCCEEDED":
            raise WarehouseError(f"statement {state}: {body.get('status')}")

        schema = body.get("manifest", {}).get("schema", {}).get("columns", [])
        columns = [(c.get("name", ""), c.get("type_text", "STRING")) for c in schema]
        return columns, body.get("result", {}).get("data_array") or []
