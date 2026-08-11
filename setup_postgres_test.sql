-- Prepares a local PostgreSQL server for Karabakh Atlas test runs.
-- Replace the placeholder password before using outside of local dev.
-- Run as: sudo -u postgres psql -f setup_postgres_test.sql
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'kba_test') THEN
    CREATE USER kba_test WITH PASSWORD 'kba_test_pwd';
  END IF;
END
$$;

SELECT 'CREATE DATABASE kba_test_db OWNER kba_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'kba_test_db')
\gexec
