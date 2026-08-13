#!/usr/bin/env python3
"""Set up the Postgres database, its schemas, roles and permissions.

Creates the database, the 'app', 'analytics' and 'analytics_dev' schemas, and a
login role per owner: 'app_user' owns 'app', 'analytics_user' owns 'analytics',
'analytics_dev_user' owns 'analytics_dev'. Each role has full access to the
schemas it owns and read-only access to the others, for both existing and future
objects.

The third role is the reason there are two analytics schemas. Trainees write
'analytics_dev' by hand while they build a mart; the scheduled pipeline writes
'analytics', which the backend reads. Giving both schemas to one role would mean
handing a trainee the credential that owns production, so they get their own.

The script is idempotent: re-running it never changes existing state, so a
failed run can simply be repeated. Existing roles keep their current password
unless you confirm a reset when asked.

Connection details come from CLI arguments or environment variables:

    POSTGRES_HOST  POSTGRES_PORT  POSTGRES_USER  POSTGRES_PASSWORD

Requires: pip install "psycopg[binary]"

Example:
    ./db-setup.py --host localhost --admin-user admin
"""

from __future__ import annotations

import argparse
import getpass
import logging
import os
import secrets
import string
import sys
from typing import NamedTuple

try:
    import psycopg
    from psycopg import sql
except ImportError:
    sys.exit('❌ Error: psycopg is required. Install it with: pip install "psycopg[binary]"')

# --- Configuration ---------------------------------------------------------

NEW_DATABASE = "project_db"  # the database this script creates
MAINTENANCE_DATABASE = "postgres"  # the database connected to while creating it

APP_SCHEMA = "app"
ANALYTICS_SCHEMA = "analytics"
ANALYTICS_DEV_SCHEMA = "analytics_dev"
APP_ROLE = "app_user"
ANALYTICS_ROLE = "analytics_user"
ANALYTICS_DEV_ROLE = "analytics_dev_user"


ROLES = (APP_ROLE, ANALYTICS_ROLE, ANALYTICS_DEV_ROLE)

# Every schema, and the role that owns it. A role gets full access to the schemas
# it owns and read-only access to all the others, so adding a schema here is the
# only edit needed - there is no second list of read-only grants to keep in sync.
SCHEMA_OWNERS = {
    APP_SCHEMA: APP_ROLE,
    ANALYTICS_SCHEMA: ANALYTICS_ROLE,
    ANALYTICS_DEV_SCHEMA: ANALYTICS_DEV_ROLE,
}


class Privileges(NamedTuple):
    """What a role may do in a schema: on the schema itself, then per object type.

    The values are SQL keywords pasted into statements, so they must stay
    trusted constants and never come from user input.
    """

    label: str  # how the grant is described in the log
    on_schema: str
    on_objects: dict[str, str]


# "ALL" on the schema (USAGE + CREATE) plus ownership of it is what lets a role
# do everything inside: create tables, views, indexes, constraints, functions.
FULL_ACCESS = Privileges("full access", "ALL",
                         {"TABLES": "ALL", "SEQUENCES": "ALL", "FUNCTIONS": "ALL"})
READ_ONLY = Privileges("read-only access", "USAGE",
                       {"TABLES": "SELECT", "SEQUENCES": "SELECT"})

PASSWORD_LENGTH = 32

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5432


# --- Logging ---------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format="%(message)s")
_log = logging.getLogger("db-setup")


def step(message: str, *args) -> None:
    """Log a task that is starting, preceded by a blank line separating sections.

    Keeping the spacing here rather than printing it in main() means it always
    lands on the log stream, in order, even when the output is piped.
    """
    _log.info("\n➡️  " + message, *args)


def done(message: str, *args) -> None:
    _log.info("✅ " + message, *args)


def skipped(message: str, *args) -> None:
    """Log a task that had nothing to do because the state already matched."""
    _log.info("⚪ " + message, *args)


def warned(message: str, *args) -> None:
    _log.warning("⚠️  " + message, *args)


def failed(message: str, *args) -> None:
    _log.error("❌ " + message, *args)


# --- Helpers ---------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    # `or` rather than a getenv default, so an empty variable falls back too.
    parser.add_argument("--host", default=os.getenv("POSTGRES_HOST") or DEFAULT_HOST)
    parser.add_argument("--port", type=int,
                        default=int(os.getenv("POSTGRES_PORT") or DEFAULT_PORT))
    parser.add_argument("--admin-user", default=os.getenv("POSTGRES_USER"),
                        help="Postgres admin/superuser account")
    parser.add_argument("--admin-password", default=os.getenv("POSTGRES_PASSWORD"),
                        help="prompted for if omitted")

    args = parser.parse_args()
    if not args.admin_user:
        parser.error("no admin user given (use --admin-user or POSTGRES_USER)")
    if not args.admin_password:
        args.admin_password = getpass.getpass(f"Password for {args.admin_user}: ")
    return args


def connect(args: argparse.Namespace, database: str) -> psycopg.Connection:
    """Open an autocommit connection (CREATE DATABASE cannot run in a transaction)."""
    return psycopg.connect(host=args.host, port=args.port, dbname=database,
                           user=args.admin_user, password=args.admin_password,
                           autocommit=True)


def execute(conn: psycopg.Connection, statement: str, **placeholders) -> None:
    conn.execute(sql.SQL(statement).format(**placeholders))


def database_exists(conn: psycopg.Connection, database: str) -> bool:
    return conn.execute("SELECT 1 FROM pg_database WHERE datname = %s",
                        (database,)).fetchone() is not None


def role_exists(conn: psycopg.Connection, role: str) -> bool:
    return conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s",
                        (role,)).fetchone() is not None


def generate_password() -> str:
    PASSWORD_ALPHABET = string.ascii_letters + string.digits
    return "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(PASSWORD_LENGTH))


# --- Steps -----------------------------------------------------------------

def create_database(conn: psycopg.Connection, database: str) -> None:
    step("Creating database '%s'", database)
    if database_exists(conn, database):
        skipped("Database '%s' already exists", database)
        return
    execute(conn, "CREATE DATABASE {database}", database=sql.Identifier(database))
    done("Created database '%s'", database)


def grant_connect(conn: psycopg.Connection, database: str, roles: list[str]) -> None:
    execute(conn, "GRANT CONNECT ON DATABASE {database} TO {roles}",
            database=sql.Identifier(database),
            roles=sql.SQL(", ").join(map(sql.Identifier, roles)))
    done("Granted CONNECT on database '%s' to %s", database, ", ".join(roles))


def confirm_password_reset(roles: list[str]) -> bool:
    """Ask whether existing roles should get freshly generated passwords."""
    warned("Roles already exist: %s", ", ".join(roles))
    if not sys.stdin.isatty():
        skipped("Not an interactive terminal, keeping the current passwords")
        return False

    # Prompt on stderr, with the log output, so stdout stays limited to the report.
    print("   Reset their passwords? Clients using the current ones will stop "
          "working [y/N]: ", end="", file=sys.stderr, flush=True)
    try:
        return input().strip().lower() in ("y", "yes")
    except EOFError:  # no answer given, keep the safe default
        print(file=sys.stderr)
        return False


def create_role(conn: psycopg.Connection, role: str) -> str:
    """Create a login role with a randomly generated password."""
    password = generate_password()
    execute(conn, "CREATE ROLE {role} LOGIN PASSWORD {password}",
            role=sql.Identifier(role), password=sql.Literal(password))
    done("Created role '%s'", role)
    return password


def reset_password(conn: psycopg.Connection, role: str) -> str:
    """Replace an existing role's password with a randomly generated one."""
    password = generate_password()
    execute(conn, "ALTER ROLE {role} PASSWORD {password}",
            role=sql.Identifier(role), password=sql.Literal(password))
    done("Reset the password of role '%s'", role)
    return password


def setup_roles(conn: psycopg.Connection, roles: list[str]) -> dict[str, str | None]:
    """Create the missing roles, and offer to reset the passwords of existing ones.

    Maps each role to its new password, or to None when an existing password was
    left untouched - so an unattended re-run still changes nothing.
    """
    existing = [role for role in roles if role_exists(conn, role)]
    reset = confirm_password_reset(existing) if existing else False

    passwords: dict[str, str | None] = {}
    for role in roles:
        if role not in existing:
            passwords[role] = create_role(conn, role)
        elif reset:
            passwords[role] = reset_password(conn, role)
        else:
            skipped("Role '%s' already exists, password left unchanged", role)
            passwords[role] = None
    return passwords


def grant_role_membership(conn: psycopg.Connection, roles: list[str], member: str) -> None:
    """Make the admin a member of the new roles, unless it is a superuser.

    Both ALTER SCHEMA ... OWNER TO and ALTER DEFAULT PRIVILEGES FOR ROLE require
    membership in the target role. Superusers are exempt; the restricted admin
    accounts of managed Postgres services are not.
    """
    if conn.execute("SELECT current_setting('is_superuser') = 'on'").fetchone()[0]:
        return

    for role in roles:
        execute(conn, "GRANT {role} TO {member}",
                role=sql.Identifier(role), member=sql.Identifier(member))
    done("Granted membership of %s to '%s'", ", ".join(roles), member)


def create_schema(conn: psycopg.Connection, schema: str, owner: str) -> None:
    execute(conn, "CREATE SCHEMA IF NOT EXISTS {schema}", schema=sql.Identifier(schema))
    execute(conn, "ALTER SCHEMA {schema} OWNER TO {owner}",
            schema=sql.Identifier(schema), owner=sql.Identifier(owner))
    done("Schema '%s' ready, owned by '%s'", schema, owner)


def grant_access(conn: psycopg.Connection, schema: str, role: str,
                 privileges: Privileges, creators: list[str]) -> None:
    """Grant `privileges` on a schema's existing and future objects to `role`."""
    execute(conn, "GRANT {privilege} ON SCHEMA {schema} TO {role}",
            privilege=sql.SQL(privileges.on_schema), schema=sql.Identifier(schema),
            role=sql.Identifier(role))

    for objects, privilege in privileges.on_objects.items():
        execute(conn, "GRANT {privilege} ON ALL {objects} IN SCHEMA {schema} TO {role}",
                privilege=sql.SQL(privilege), objects=sql.SQL(objects),
                schema=sql.Identifier(schema), role=sql.Identifier(role))
        # Default privileges apply only to objects created by one specific role,
        # so they have to be registered for every role that creates objects here.
        for creator in creators:
            execute(conn,
                    "ALTER DEFAULT PRIVILEGES FOR ROLE {creator} IN SCHEMA {schema} "
                    "GRANT {privilege} ON {objects} TO {role}",
                    creator=sql.Identifier(creator), schema=sql.Identifier(schema),
                    privilege=sql.SQL(privilege), objects=sql.SQL(objects),
                    role=sql.Identifier(role))

    done("Granted %s on schema '%s' to '%s'", privileges.label, schema, role)


def report(args: argparse.Namespace, passwords: dict[str, str | None]) -> None:
    unchanged = "(unchanged)"
    print(f"\n✅ Setup complete on {args.host}:{args.port}\n")
    print(f"  database : {NEW_DATABASE}")
    print(f"  schemas  : {', '.join(SCHEMA_OWNERS)}\n")
    for role in ROLES:
        owned = [s for s, owner in SCHEMA_OWNERS.items() if owner == role]
        read_only = [s for s in SCHEMA_OWNERS if s not in owned]
        print(f"  {role}")
        print(f"    password : {passwords[role] or unchanged}")
        print(f"    access   : full on {', '.join(owned)} — "
              f"read-only on {', '.join(read_only)}")


# --- Entry point -----------------------------------------------------------

def main() -> None:
    args = parse_args()
    roles = list(ROLES)

    step("Connecting to %s:%s as '%s'", args.host, args.port, args.admin_user)
    with connect(args, MAINTENANCE_DATABASE) as conn:
        done("Connected to PostgreSQL %s",
             conn.execute("SHOW server_version").fetchone()[0])

        create_database(conn, NEW_DATABASE)

        # Roles live in the cluster, not in the database, so create them here.
        step("Creating roles: %s", ", ".join(roles))
        passwords = setup_roles(conn, roles)
        grant_role_membership(conn, roles, args.admin_user)
        # A database-level grant, so it does not need the connection below.
        grant_connect(conn, NEW_DATABASE, roles)

    with connect(args, NEW_DATABASE) as conn:
        step("Creating schemas:")
        for schema, owner in SCHEMA_OWNERS.items():
            create_schema(conn, schema, owner)

        step("Granting schema privileges")
        creators = [args.admin_user, *roles]
        for schema, owner in SCHEMA_OWNERS.items():
            for role in roles:
                grant_access(conn, schema, role,
                             FULL_ACCESS if role == owner else READ_ONLY, creators)

    report(args, passwords)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        failed("Cancelled")
        sys.exit(130)
    except psycopg.OperationalError as error:
        failed("Could not connect to Postgres: %s", str(error).strip())
        sys.exit(1)
    except Exception as error:  # noqa: BLE001 - top-level guard for a CLI script
        failed("Setup failed: %s: %s", type(error).__name__, str(error).strip())
        sys.exit(1)
