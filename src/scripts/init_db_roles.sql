-- Initialize least-privilege roles and databases for development and testing
CREATE DATABASE leadflow_dev;
CREATE DATABASE leadflow_test;

-- 1. Create non-superuser roles with strict privilege boundaries
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'leadflow_migrator') THEN
        CREATE ROLE leadflow_migrator LOGIN PASSWORD 'dev_migrator_pw' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'leadflow_reader') THEN
        CREATE ROLE leadflow_reader LOGIN PASSWORD 'dev_reader_pw' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'leadflow_writer') THEN
        CREATE ROLE leadflow_writer LOGIN PASSWORD 'dev_writer_pw' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
    END IF;
END
$$;

-- 2. Grant database connection privileges
GRANT ALL PRIVILEGES ON DATABASE leadflow_dev TO leadflow_migrator;
GRANT ALL PRIVILEGES ON DATABASE leadflow_test TO leadflow_migrator;
GRANT CONNECT ON DATABASE leadflow_dev TO leadflow_reader, leadflow_writer;
GRANT CONNECT ON DATABASE leadflow_test TO leadflow_reader, leadflow_writer;

-- 3. Configure pgvector and default privileges inside leadflow_dev
\connect leadflow_dev
CREATE EXTENSION IF NOT EXISTS vector;
GRANT USAGE, CREATE ON SCHEMA public TO leadflow_migrator;
GRANT USAGE ON SCHEMA public TO leadflow_reader, leadflow_writer;

ALTER DEFAULT PRIVILEGES FOR ROLE leadflow_migrator IN SCHEMA public
    GRANT SELECT ON TABLES TO leadflow_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE leadflow_migrator IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO leadflow_writer;
ALTER DEFAULT PRIVILEGES FOR ROLE leadflow_migrator IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO leadflow_writer;

-- 4. Configure pgvector and default privileges inside leadflow_test
\connect leadflow_test
CREATE EXTENSION IF NOT EXISTS vector;
GRANT USAGE, CREATE ON SCHEMA public TO leadflow_migrator;
GRANT USAGE ON SCHEMA public TO leadflow_reader, leadflow_writer;

ALTER DEFAULT PRIVILEGES FOR ROLE leadflow_migrator IN SCHEMA public
    GRANT SELECT ON TABLES TO leadflow_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE leadflow_migrator IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO leadflow_writer;
ALTER DEFAULT PRIVILEGES FOR ROLE leadflow_migrator IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO leadflow_writer;