-- Local development only. Postgres runs every .sql in this folder the first
-- time it creates its data directory, so the compose database comes up with
-- somewhere for the pipeline to publish to.
--
-- On the real database these schemas come from the backend's Flyway migration,
-- together with the roles and grants that keep the two sides apart. None of
-- that is reproduced here: locally you are the superuser and the point is to
-- have the pipeline's last step runnable, not to rehearse the permissions.
--
-- `analytics` is where the scheduled run publishes. `analytics_dev` is yours:
-- point BACKEND_PG_PUBLISH_SCHEMA at it while you are working, and you can
-- rebuild it as often as you like without touching what the backend reads.

CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS analytics_dev;

-- The other direction: views the backend chooses to expose to the pipeline.
-- Empty here until the backend team adds one.
CREATE SCHEMA IF NOT EXISTS app;
