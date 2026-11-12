-- Runs once, when the pgdata volume is first created (docker compose down -v to rerun).
-- Enables pgvector in the dev database and creates a separate database for pytest,
-- so a test run can never touch dev data.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE DATABASE store_test;
\connect store_test
CREATE EXTENSION IF NOT EXISTS vector;
