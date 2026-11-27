-- Separate database roles for staging/production (run once as a PostgreSQL administrator).
-- Replace the passwords with strong secrets from your hosting provider's secret store.
--
--   vittasynx_migrator  owns the schema; used ONLY to run `alembic upgrade head`
--                       (set VX_MIGRATION_DATABASE_URL to this role).
--   vittasynx_app       the running application (VX_DATABASE_URL). Not the table owner, not a
--                       superuser, no BYPASSRLS, and no DELETE/TRUNCATE on financial history.
--
-- Usage: psql "$ADMIN_URL" -v migrator_pw="'...'" -v app_pw="'...'" -v db=vittasynx -f roles.sql

CREATE ROLE vittasynx_migrator LOGIN PASSWORD :migrator_pw NOSUPERUSER NOBYPASSRLS NOCREATEROLE;
CREATE ROLE vittasynx_app      LOGIN PASSWORD :app_pw      NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB;

ALTER DATABASE :db OWNER TO vittasynx_migrator;
\connect :db
ALTER SCHEMA public OWNER TO vittasynx_migrator;
GRANT USAGE ON SCHEMA public TO vittasynx_app;

-- Run the grants below AFTER `alembic upgrade head` has created the tables (and again after
-- any migration that adds tables), connected as vittasynx_migrator:

-- Read/write on everything by default…
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO vittasynx_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO vittasynx_app;
-- …DELETE only where the application legitimately removes rows:
GRANT DELETE ON memberships, mfa_recovery_codes, rate_limit_hits TO vittasynx_app;
-- Financial history (invoices, invoice_versions, credit_notes, payments, allocations,
-- audit_events, stored_files, file_blobs) gets no DELETE at all.
REVOKE UPDATE ON audit_events, invoice_versions FROM vittasynx_app;
