-- Prepares a local PostgreSQL server for Karabakh Atlas development.
-- Replace the placeholder password before using outside of local dev.
CREATE DATABASE kba_dev_db;
DO
$$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'kba_dev') THEN
      CREATE USER kba_dev WITH PASSWORD 'kba_dev_pwd';
   END IF;
END
$$;
GRANT ALL PRIVILEGES ON DATABASE kba_dev_db TO kba_dev;
