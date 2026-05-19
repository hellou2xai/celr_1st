"""asyncpg connection pool used by the FastAPI app and the MCP server."""
from __future__ import annotations

import os
import asyncpg


_pool: asyncpg.Pool | None = None


def _dsn() -> str:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL is not set")
    if dsn.startswith("postgres://"):
        dsn = "postgresql://" + dsn[len("postgres://"):]
    return dsn


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=_dsn(),
            min_size=1,
            max_size=int(os.environ.get("DB_POOL_MAX", "8")),
            command_timeout=120,
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def fetch(sql: str, *args) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *args)
        return [_jsonable(dict(r)) for r in rows]


async def fetchrow(sql: str, *args) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, *args)
        return _jsonable(dict(row)) if row else None


def _jsonable(d: dict) -> dict:
    """Coerce Decimals, datetimes, dates to JSON-friendly types."""
    import datetime
    import decimal
    out = {}
    for k, v in d.items():
        if isinstance(v, decimal.Decimal):
            out[k] = float(v)
        elif isinstance(v, (datetime.datetime, datetime.date)):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out
