-- Local development only. Postgres runs every .sql in this folder the first
-- time it creates its data directory, so the compose database comes up with
-- somewhere for the pipeline to publish to.
--
-- On the real database `analytics` is created once, by hand, when the database
-- is deployed, together with the two roles and their grants. None of that is
-- reproduced here: locally you are the superuser and the point is to have the
-- pipeline's last step runnable, not to rehearse the permissions.
--
-- `analytics` is where the scheduled run publishes. `analytics_dev` is yours:
-- point BACKEND_PG_PUBLISH_SCHEMA at it while you are working, and you can
-- rebuild it as often as you like without touching what the backend reads.

CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS analytics_dev;
