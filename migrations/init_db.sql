-- CityMind initial schema.
-- Targets PostgreSQL 15 + TimescaleDB (for metrics / weather timeseries).
-- If TimescaleDB is not installed the `create_hypertable` calls are no-ops;
-- the rest of the schema remains valid plain Postgres.

CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

--------------------------------------------------------------------------
-- Core reference tables
--------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS cities (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    region          TEXT NOT NULL,
    population      INTEGER,
    lat             DOUBLE PRECISION,
    lon             DOUBLE PRECISION,
    timezone        TEXT NOT NULL DEFAULT 'Europe/Moscow',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sources (
    id              SERIAL PRIMARY KEY,
    city_id         INTEGER NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    kind            TEXT NOT NULL,       -- telegram | vk | news_rss | gosuslugi
    handle          TEXT NOT NULL,
    name            TEXT,
    category        TEXT,
    priority        TEXT NOT NULL DEFAULT 'P1',
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (city_id, kind, handle)
);

--------------------------------------------------------------------------
-- Collected content
--------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS news (
    id              TEXT PRIMARY KEY,    -- hash from collector
    city_id         INTEGER NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    source_id       INTEGER REFERENCES sources(id) ON DELETE SET NULL,
    source_kind     TEXT NOT NULL,
    source_handle   TEXT NOT NULL,
    title           TEXT,
    content         TEXT,
    url             TEXT,
    author          TEXT,
    category        TEXT,
    published_at    TIMESTAMPTZ NOT NULL,
    sentiment       REAL,                -- [-1, +1], filled by NLP pass
    collected_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS news_city_published_idx
    ON news (city_id, published_at DESC);
CREATE INDEX IF NOT EXISTS news_category_idx ON news (category);
CREATE INDEX IF NOT EXISTS news_content_trgm_idx
    ON news USING gin (content gin_trgm_ops);

CREATE TABLE IF NOT EXISTS appeals (
    id              TEXT PRIMARY KEY,
    city_id         INTEGER NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    source          TEXT NOT NULL,       -- gosuslugi | vk_dm | telegram_bot | ...
    author          TEXT,
    title           TEXT,
    content         TEXT,
    category        TEXT,
    status          TEXT NOT NULL DEFAULT 'new', -- new | in_progress | resolved
    sentiment       REAL,
    published_at    TIMESTAMPTZ NOT NULL,
    collected_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

--------------------------------------------------------------------------
-- Timeseries metrics
--------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS metrics (
    city_id         INTEGER NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sb              REAL,  -- Безопасность
    tf              REAL,  -- Экономика
    ub              REAL,  -- Качество жизни
    chv             REAL,  -- Социальный капитал
    trust_index     REAL,
    happiness_index REAL,
    PRIMARY KEY (city_id, ts)
);

SELECT create_hypertable('metrics', 'ts', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS weather (
    city_id         INTEGER NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    temperature     REAL,
    feels_like      REAL,
    humidity        INTEGER,
    wind_speed      REAL,
    condition       TEXT,
    condition_emoji TEXT,
    comfort_index   REAL,
    raw             JSONB,
    PRIMARY KEY (city_id, ts)
);

SELECT create_hypertable('weather', 'ts', if_not_exists => TRUE);

--------------------------------------------------------------------------
-- Analytics outputs
--------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS loops (
    id              BIGSERIAL PRIMARY KEY,
    city_id         INTEGER NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    name            TEXT NOT NULL,
    description     TEXT,
    strength        REAL,
    break_points    JSONB
);

CREATE TABLE IF NOT EXISTS agendas (
    id              BIGSERIAL PRIMARY KEY,
    city_id         INTEGER NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    kind            TEXT NOT NULL, -- daily | weekly | critical | strategic
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    headline        TEXT NOT NULL,
    description     TEXT,
    actions         JSONB NOT NULL DEFAULT '[]'::jsonb,
    payload         JSONB
);

CREATE INDEX IF NOT EXISTS agendas_city_kind_idx
    ON agendas (city_id, kind, created_at DESC);

CREATE TABLE IF NOT EXISTS roadmaps (
    id              BIGSERIAL PRIMARY KEY,
    city_id         INTEGER NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    vector          TEXT NOT NULL,
    start_level     REAL NOT NULL,
    target_level    REAL NOT NULL,
    deadline        DATE NOT NULL,
    scenario        TEXT NOT NULL DEFAULT 'baseline',
    total_cost_rub  BIGINT NOT NULL DEFAULT 0,
    payload         JSONB NOT NULL
);

--------------------------------------------------------------------------
-- Users and auth
--------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    email           TEXT NOT NULL UNIQUE,
    full_name       TEXT,
    role            TEXT NOT NULL DEFAULT 'viewer',  -- admin | mayor | deputy | analyst | viewer
    password_hash   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at   TIMESTAMPTZ
);

--------------------------------------------------------------------------
-- Retention
--------------------------------------------------------------------------

-- Drop news older than 12 months if TimescaleDB retention policy is enabled.
-- These statements are no-ops on plain Postgres.
DO $$
BEGIN
    PERFORM add_retention_policy('metrics', INTERVAL '365 days', if_not_exists => TRUE);
    PERFORM add_retention_policy('weather', INTERVAL '365 days', if_not_exists => TRUE);
EXCEPTION WHEN undefined_function THEN
    NULL;
END $$;
