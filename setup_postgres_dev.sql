-- Prepares a local PostgreSQL server for Karabakh Atlas development.
-- Replace the placeholder password before using outside of local dev.
-- Run as: sudo -u postgres psql -f setup_postgres_dev.sql
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'kba_dev') THEN
    CREATE USER kba_dev WITH PASSWORD 'kba_dev_pwd';
  END IF;
END
$$;

SELECT 'CREATE DATABASE kba_dev_db OWNER kba_dev'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'kba_dev_db')
\gexec
