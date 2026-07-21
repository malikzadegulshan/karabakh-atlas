-- Prepares a local MySQL server for Karabakh Atlas development.
-- Replace the placeholder password before using outside of local dev.
CREATE DATABASE IF NOT EXISTS kba_dev_db;
CREATE USER IF NOT EXISTS 'kba_dev'@'localhost' IDENTIFIED BY 'kba_dev_pwd';
GRANT ALL PRIVILEGES ON kba_dev_db.* TO 'kba_dev'@'localhost';
GRANT SELECT ON performance_schema.* TO 'kba_dev'@'localhost';
FLUSH PRIVILEGES;
