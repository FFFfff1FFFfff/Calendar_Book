import asyncpg

_pool: asyncpg.Pool | None = None

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS calendar_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id UUID NOT NULL,
    slug TEXT NOT NULL,
    google_access_token TEXT NOT NULL,
    google_refresh_token TEXT NOT NULL,
    token_expires_at TIMESTAMPTZ,
    google_email TEXT,
    timezone TEXT DEFAULT 'UTC',
    business_hours_start TEXT DEFAULT '09:00',
    business_hours_end TEXT DEFAULT '17:00',
    slot_duration_minutes INT DEFAULT 30,
    connected_at TIMESTAMPTZ DEFAULT now(),
    is_valid BOOLEAN DEFAULT true
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_cc_owner ON calendar_connections(owner_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_cc_slug ON calendar_connections(slug);
"""

MIGRATE_SQL = """
DO $$
BEGIN
    -- Migrate from Nylas schema to direct Google tokens
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'calendar_connections' AND column_name = 'nylas_grant_id'
    ) THEN
        ALTER TABLE calendar_connections ADD COLUMN IF NOT EXISTS google_access_token TEXT;
        ALTER TABLE calendar_connections ADD COLUMN IF NOT EXISTS google_refresh_token TEXT;
        ALTER TABLE calendar_connections ADD COLUMN IF NOT EXISTS token_expires_at TIMESTAMPTZ;
        ALTER TABLE calendar_connections DROP COLUMN IF EXISTS nylas_grant_id;
        -- Invalidate old connections (they need to re-auth)
        UPDATE calendar_connections SET is_valid = false
            WHERE google_refresh_token IS NULL;
    END IF;
END $$;
"""


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        raise RuntimeError("Database pool not initialised – call init_pool() first")
    return _pool


async def init_pool(dsn: str) -> None:
    global _pool
    _pool = await asyncpg.create_pool(
        dsn, min_size=0, max_size=5, timeout=30, command_timeout=30,
    )
    async with _pool.acquire(timeout=30) as conn:
        await conn.execute(MIGRATE_SQL)
        await conn.execute(SCHEMA_SQL)


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
