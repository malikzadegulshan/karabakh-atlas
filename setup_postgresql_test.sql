-- Prepares a local PostgreSQL server for Karabakh Atlas test runs.
-- Replace the placeholder password before using outside of local dev.
CREATE DATABASE kba_test_db;
DO
$$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'kba_test') THEN
      CREATE USER kba_test WITH PASSWORD 'kba_test_pwd';
   END IF;
END
$$;
GRANT ALL PRIVILEGES ON DATABASE kba_test_db TO kba_test;
