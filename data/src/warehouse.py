"""Run SQL against your team's Databricks SQL warehouse over HTTP.

Why this exists when dbt already talks to the warehouse: dbt runs SQL that
describes tables. Some steps are not describable that way. The enrichment job
classifies a job title in Python, and the publish step copies rows out to
another database entirely. Both need to send a statement and read the answer
back from ordinary Python.

This uses the Statement Execution API, which is plain HTTPS. The alternative,
`databricks-sql-connector`, speaks Thrift over a much larger dependency tree,
and gives you nothing extra for statements this small.

Authentication, and the one thing that surprises everybody
----------------------------------------------------------
Your team has a service principal. It authenticates at Microsoft Entra, not at
the Databricks workspace: the workspace's own `/oidc/v1/token` endpoint returns
401 for principals created this way, and the error does not hint that you are
knocking on the wrong door. So the token comes from

    https://login.microsoftonline.com/<tenant>/oauth2/v2.0/token

with the scope below, which is the fixed application id of Azure Databricks.
It is the same for every workspace in the world, so it is a constant here
rather than a setting.

These are the same DATABRICKS_CLIENT_ID and DATABRICKS_CLIENT_SECRET that dbt
uses. One credential, one place to rotate it.
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

# How long the API may block before it answers "still running". Anything
# longer than 50s is rejected by the API.
WAIT_TIMEOUT = "50s"


class WarehouseError(RuntimeError):
    """A statement did not succeed."""


class Queryable(Protocol):
    """What the steps downstream actually need from a warehouse.

    Two methods and a catalog name. Depending on this rather than on the class
    below is what lets the tests hand `enrich` and `publish_results` a fake
    that records statements instead of sending them, with no mocking library
    and no network. Anything with these three members fits.
    """

    catalog: str

    def run(self, statement: str) -> list[list]: ...

    def query(self, statement: str) -> tuple[list[tuple[str, str]], list[list]]: ...


def warehouse_id(http_path: str) -> str:
    """Pull the warehouse id out of the path dbt already needs.

    `DATABRICKS_HTTP_PATH` looks like /sql/1.0/warehouses/0aae52a375e34214.
    Deriving the id from it means there is one warehouse setting rather than
    two that can disagree.
    """
    identifier = http_path.rstrip("/").rsplit("/", 1)[-1]
    if not identifier:
        raise ValueError(f"cannot read a warehouse id out of {http_path!r}")
    return identifier


def entra_token(
    tenant_id: str, client_id: str, client_secret: str, opener=urllib.request.urlopen
) -> str:
    """Exchange the team service principal for a Databricks access token."""
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

    Built from the environment by `from_env()`, or directly in tests with a
    fake `opener`, which is the only reason that argument exists.
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
        """Build from the same variables dbt reads, so there is one set.

        `.env` is loaded here rather than being assumed. Running this from a
        laptop is the normal case while you are developing, and a job that
        cannot see the file you just filled in is a confusing first failure.
        In Azure there is no `.env` and this does nothing.
        """
        load_dotenv()
        missing = [
            name
            for name in (
                "DATABRICKS_HOST",
                "DATABRICKS_HTTP_PATH",
                "DATABRICKS_CATALOG",
                "DATABRICKS_CLIENT_ID",
                "DATABRICKS_CLIENT_SECRET",
            )
            if not os.getenv(name)
        ]
        if missing:
            raise WarehouseError(
                "missing settings: " + ", ".join(missing) + ". "
                "These are the same values dbt uses; read the two credential "
                "ones from Key Vault."
            )
        token = entra_token(
            tenant_id=os.getenv("AZURE_TENANT_ID", ""),
            client_id=os.environ["DATABRICKS_CLIENT_ID"],
            client_secret=os.environ["DATABRICKS_CLIENT_SECRET"],
            opener=opener,
        )
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
        """Run one statement and return its rows, waiting for it to finish.

        Rows come back as lists of strings, which is what the API sends. Cast
        them where you use them, close to the column you know the type of.
        """
        return self.query(statement)[1]

    def query(self, statement: str) -> tuple[list[tuple[str, str]], list[list]]:
        """Run one statement and return its columns as well as its rows.

        Columns are (name, type) pairs, taken from what the warehouse says it
        returned rather than from anything written down here. The publish step
        uses them to build a matching table in Postgres, so adding a column to
        the mart does not mean editing the sync as well.

        The API answers immediately with PENDING or RUNNING for anything that
        takes longer than `WAIT_TIMEOUT`, so this polls. Returning before the
        statement finished is the bug this avoids: the next step would build on
        a table that is still being written.
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
        columns = [(column.get("name", ""), column.get("type_text", "STRING")) for column in schema]
        return columns, body.get("result", {}).get("data_array") or []
