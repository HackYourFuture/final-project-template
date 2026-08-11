-- The boundary between the backend and the data pipeline.
--
-- The backend owns the application tables. The data team owns one schema next
-- to them, `analytics`, and publishes its marts there. Neither side writes the
-- other's tables, which is what stops a migration and a nightly sync from
-- quietly undoing each other.
--
-- This lives in the backend repository, as a migration, so the setup is
-- reproducible instead of being a console command somebody ran once.
--
-- Three placeholders. Set them in your Flyway configuration and take the
-- values from Key Vault. Never put a password in this file: it is committed.
--   flyway.placeholders.app_role=                  the role the backend logs in as
--   flyway.placeholders.analytics_writer_password=
--   flyway.placeholders.analytics_reader_password=

CREATE SCHEMA IF NOT EXISTS analytics;

-- CREATE ROLE has no IF NOT EXISTS, and roles live at cluster level, so a
-- second database on the same server would make this migration fail without
-- the guard.
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'analytics_writer') THEN
        CREATE ROLE analytics_writer LOGIN PASSWORD '${analytics_writer_password}';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'analytics_reader') THEN
        CREATE ROLE analytics_reader LOGIN PASSWORD '${analytics_reader_password}';
    END IF;
END
$$;

-- Writes marts, and can reach nothing else.
GRANT ALL PRIVILEGES ON SCHEMA analytics TO analytics_writer;

-- The application reads the marts but can never change them.
GRANT USAGE ON SCHEMA analytics TO ${app_role};
GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO ${app_role};

-- FOR ROLE analytics_writer is the part that makes this work. Without it the
-- rule only covers tables created by whoever ran this migration, and the sync
-- creates a brand new table on every publish, so the application would be
-- locked out of its own marts.
ALTER DEFAULT PRIVILEGES FOR ROLE analytics_writer IN SCHEMA analytics
    GRANT SELECT ON TABLES TO ${app_role};

-- Reads the application's tables, and writes nothing at all. The pipeline uses
-- this to copy rows into its own warehouse, never to build tables here.
GRANT USAGE ON SCHEMA public TO analytics_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO analytics_reader;

-- Same reasoning as above, in the other direction: without this, a table you
-- add next week is invisible to the inbound sync until someone re-runs the
-- grant by hand.
ALTER DEFAULT PRIVILEGES FOR ROLE ${app_role} IN SCHEMA public
    GRANT SELECT ON TABLES TO analytics_reader;
