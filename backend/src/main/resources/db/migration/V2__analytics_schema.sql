-- The boundary between the backend and the data pipeline.
--
-- Two schemas, and each side owns the one it writes:
--
--   analytics   the data team writes, this application reads. Published marts.
--   app         this application writes, the data team reads. Views over
--               `public` that we choose to expose.
--
-- `public` stays private. Nothing outside this application reads it.
--
-- That symmetry is the point. If the pipeline selected straight from our
-- tables, renaming a column here would break their 6am run and nobody would
-- know until the numbers went stale. A view is a promise; changing one is a
-- visible act. It also means anything sensitive is hashed or dropped in the
-- view, so it never leaves this database at all, rather than being discarded
-- by someone else after the fact.
--
-- This lives in the backend repository, as a migration, so the setup is
-- reproducible instead of being a console command somebody ran once.
--
-- One placeholder. Set it in your Flyway configuration:
--   flyway.placeholders.app_role=   the role this application logs in as
--
-- There are deliberately no password placeholders here. See the roles below.
--
-- Privileges required to run this migration: CREATEROLE, because roles are
-- created, and ownership of (or membership in) the roles named in ALTER
-- DEFAULT PRIVILEGES. On Azure Database for PostgreSQL the server
-- administrator has both. A plain application login does not, so run this as
-- the admin the same way you run every other migration.

-- Roles are cluster-wide, not per database, and CREATE ROLE has no
-- IF NOT EXISTS, so a second database on the same server would make this fail
-- without the guard.
--
-- No passwords are set here on purpose. A password in a migration is a
-- password in git, and passing one as a placeholder only moves the problem:
-- the value ends up inside a single-quoted SQL literal, so a rotated password
-- containing a quote breaks the migration in a way that is genuinely hard to
-- diagnose. These roles can log in but cannot authenticate until a password is
-- set out of band, which is what the provisioning script does when it writes
-- them to Key Vault.
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'analytics_writer') THEN
        CREATE ROLE analytics_writer LOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_reader') THEN
        CREATE ROLE app_reader LOGIN;
    END IF;
END
$$;

-- ---------------------------------------------------------------------------
-- Outbound: the data team publishes here, we read.
-- ---------------------------------------------------------------------------

-- Owned by the role that writes it. Without AUTHORIZATION the schema belongs
-- to whoever ran the migration, and if that happens to be the application's
-- own login then the application can drop the marts it is only supposed to
-- read.
CREATE SCHEMA IF NOT EXISTS analytics AUTHORIZATION analytics_writer;

GRANT USAGE ON SCHEMA analytics TO ${app_role};
GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO ${app_role};

-- FOR ROLE analytics_writer is the part that makes this work, and getting it
-- wrong is silent. Default privileges apply to the role that creates the
-- object, not to the role that ran the statement. The publish step creates a
-- brand new table on every run, so without naming the writer here the
-- application is locked out of every mart, on every run, forever.
ALTER DEFAULT PRIVILEGES FOR ROLE analytics_writer IN SCHEMA analytics
    GRANT SELECT ON TABLES TO ${app_role};

-- ---------------------------------------------------------------------------
-- Inbound: we publish here, the data team reads.
-- ---------------------------------------------------------------------------

CREATE SCHEMA IF NOT EXISTS app AUTHORIZATION ${app_role};

GRANT USAGE ON SCHEMA app TO app_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA app TO app_reader;

-- Same reasoning as above, in the other direction: a view added next week is
-- invisible to the inbound sync until someone remembers to re-run a grant.
--
-- Two statements, because objects in this schema can be created by either of
-- two roles and default privileges only ever cover one. Views added by a later
-- migration belong to whoever runs migrations; views created by the running
-- application belong to ${app_role}. Naming only one of them leaves the other
-- half invisible to the sync, which fails as a permission error on a view that
-- is plainly there.
ALTER DEFAULT PRIVILEGES IN SCHEMA app
    GRANT SELECT ON TABLES TO app_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE ${app_role} IN SCHEMA app
    GRANT SELECT ON TABLES TO app_reader;

-- Add one view per thing you agree to share, and nothing more. Shape it for
-- them rather than exposing the table: drop the columns they do not need, and
-- hash anything that identifies a person, so the raw value never leaves here.
--
-- CREATE OR REPLACE VIEW app.saved_jobs AS
-- SELECT
--     id,
--     encode(digest(user_id::text, 'sha256'), 'hex') AS user_hash,
--     job_slug,
--     saved_at
-- FROM public.saved_jobs;
