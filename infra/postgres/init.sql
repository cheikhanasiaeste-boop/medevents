-- Postgres extensions enabled at first boot.
-- (Alembic also enables them defensively in 0001, but having them
-- ready at boot lets us verify docker is healthy before migrations run.)
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS citext;
