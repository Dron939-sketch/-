-- Городской Разум — initial schema.
-- Targets PostgreSQL 15. Every optional piece (pg_trgm index, TimescaleDB
-- hypertables) is wrapped in a DO block with `WHEN OTHERS` so a missing
-- extension or limited privileges never aborts the whole migration.
--
-- The file is split into segments by `-- @SEGMENT ...` marker lines.
-- `db.seed.run_migrations` executes each segment in its own transaction,
-- so a failure in one segment (e.g. an unsupported TimescaleDB feature
-- on Apache edition) doesn't roll back the previous ones.

-- @SEGMENT extensions
-- pg_trgm powers the fuzzy search index on news.content below. If it's
-- not available we skip that one index but the schema stays valid.
DO $$
BEGIN
    EXECUTE 'CREATE EXTENSION IF NOT EXISTS pg_trgm';
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'pg_trgm extension unavailable (%) — trigram search index skipped', SQLERRM;
END $$;

DO $$
BEGIN
    EXECUTE 'CREATE EXTENSION IF NOT EXISTS timescaledb';
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'TimescaleDB extension unavailable (%) — using plain Postgres', SQLERRM;
END $$;

-- @SEGMENT core_tables
CREATE TABLE IF NOT EXISTS cities (
    id              SERIAL PRIMARY KEY,
    slug            TEXT UNIQUE,
    name            TEXT NOT NULL UNIQUE,
    region          TEXT NOT NULL,
    population      INTEGER,
    lat             DOUBLE PRECISION,
    lon             DOUBLE PRECISION,
    timezone        TEXT NOT NULL DEFAULT 'Europe/Moscow',
    emoji           TEXT,
    accent_color    TEXT,
    is_pilot        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE cities ADD COLUMN IF NOT EXISTS slug TEXT;
ALTER TABLE cities ADD COLUMN IF NOT EXISTS emoji TEXT;
ALTER TABLE cities ADD COLUMN IF NOT EXISTS accent_color TEXT;
ALTER TABLE cities ADD COLUMN IF NOT EXISTS is_pilot BOOLEAN NOT NULL DEFAULT FALSE;
CREATE UNIQUE INDEX IF NOT EXISTS cities_slug_uniq ON cities (slug)
    WHERE slug IS NOT NULL;

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

-- @SEGMENT news_table
CREATE TABLE IF NOT EXISTS news (
    id              TEXT PRIMARY KEY,
    city_id         INTEGER NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    source_kind     TEXT NOT NULL,
    source_handle   TEXT NOT NULL,
    title           TEXT,
    content         TEXT,
    url             TEXT,
    author          TEXT,
    category        TEXT,
    published_at    TIMESTAMPTZ NOT NULL,
    sentiment       REAL,
    severity        REAL,
    summary         TEXT,
    enrichment      JSONB,
    collected_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE news ADD COLUMN IF NOT EXISTS severity REAL;
ALTER TABLE news ADD COLUMN IF NOT EXISTS summary TEXT;
ALTER TABLE news ADD COLUMN IF NOT EXISTS enrichment JSONB;

CREATE INDEX IF NOT EXISTS news_city_published_idx
    ON news (city_id, published_at DESC);
CREATE INDEX IF NOT EXISTS news_category_idx ON news (category);

-- @SEGMENT news_trigram_index
-- Trigram index depends on pg_trgm — isolated segment so a missing
-- extension doesn't affect anything else.
DO $$
BEGIN
    EXECUTE 'CREATE INDEX IF NOT EXISTS news_content_trgm_idx '
            'ON news USING gin (content gin_trgm_ops)';
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'trigram index on news.content skipped (%): ok without pg_trgm', SQLERRM;
END $$;

-- @SEGMENT appeals_table
CREATE TABLE IF NOT EXISTS appeals (
    id              TEXT PRIMARY KEY,
    city_id         INTEGER NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    source          TEXT NOT NULL,
    author          TEXT,
    title           TEXT,
    content         TEXT,
    category        TEXT,
    status          TEXT NOT NULL DEFAULT 'new',
    sentiment       REAL,
    published_at    TIMESTAMPTZ NOT NULL,
    collected_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- @SEGMENT metrics_table
CREATE TABLE IF NOT EXISTS metrics (
    city_id         INTEGER NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sb              REAL,
    tf              REAL,
    ub              REAL,
    chv             REAL,
    trust_index     REAL,
    happiness_index REAL,
    PRIMARY KEY (city_id, ts)
);

CREATE INDEX IF NOT EXISTS metrics_city_ts_idx ON metrics (city_id, ts DESC);

-- @SEGMENT metrics_hypertable
DO $$
BEGIN
    PERFORM create_hypertable('metrics', 'ts', if_not_exists => TRUE);
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'metrics hypertable skipped (%): staying as a regular table', SQLERRM;
END $$;

-- @SEGMENT weather_table
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

CREATE INDEX IF NOT EXISTS weather_city_ts_idx ON weather (city_id, ts DESC);

-- @SEGMENT weather_hypertable
DO $$
BEGIN
    PERFORM create_hypertable('weather', 'ts', if_not_exists => TRUE);
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'weather hypertable skipped (%): staying as a regular table', SQLERRM;
END $$;

-- @SEGMENT analytics_tables
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
    kind            TEXT NOT NULL,
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

-- @SEGMENT users_table
CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    email           TEXT NOT NULL UNIQUE,
    full_name       TEXT,
    role            TEXT NOT NULL DEFAULT 'viewer',
    password_hash   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at   TIMESTAMPTZ
);

-- Retention policies removed: on TimescaleDB Apache edition
-- add_retention_policy raises FeatureNotSupportedError (Enterprise-only)
-- before the DO block's exception handler can see it. We don't need
-- retention for the MVP — row count is modest for 6 cities × 1h snapshots.
