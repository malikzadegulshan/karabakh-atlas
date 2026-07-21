-- Prepares a local MySQL server for Karabakh Atlas test runs.
-- Replace the placeholder password before using outside of local dev.
CREATE DATABASE IF NOT EXISTS kba_test_db;
CREATE USER IF NOT EXISTS 'kba_test'@'localhost' IDENTIFIED BY 'kba_test_pwd';
GRANT ALL PRIVILEGES ON kba_test_db.* TO 'kba_test'@'localhost';
GRANT SELECT ON performance_schema.* TO 'kba_test'@'localhost';
FLUSH PRIVILEGES;
