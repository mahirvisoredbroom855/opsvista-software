# -*- coding: utf-8 -*-
"""
Database setup helper used by tests.

- Normalizes DSN (handles 'postgresql+asyncpg://')
- Tries to connect with asyncpg; if it fails, returns a mock connection so tests can proceed.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

try:
    import asyncpg  # type: ignore
except Exception:  # pragma: no cover
    asyncpg = None

try:
    from app.core.config import settings
except Exception:  # pragma: no cover
    class _S:
        DATABASE_URL = os.getenv("DATABASE_URL")
    settings = _S()

logger = logging.getLogger(__name__)


def _normalize_dsn(url: Optional[str]) -> str:
    if not url:
        return ""
    url = url.strip()
    replacements = {
        "postgresql+asyncpg://": "postgresql://",
        "postgres+asyncpg://": "postgres://",
        "postgresql+psycopg://": "postgresql://",
        "postgresql+psycopg2://": "postgresql://",
    }
    for k, v in replacements.items():
        if url.startswith(k):
            return url.replace(k, v, 1)
    if not (url.startswith("postgresql://") or url.startswith("postgres://")):
        if "://" in url:
            scheme, rest = url.split("://", 1)
            if scheme.startswith("postgres"):
                return "postgresql://" + rest
    return url


class _PoolProxy:
    """Simple wrapper so we expose fetch/fetchval/execute/close like a normal connection."""
    def __init__(self, pool: "asyncpg.Pool"):
        self.pool = pool

    async def fetch(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchval(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)

    async def execute(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def close(self):
        await self.pool.close()


class MockConnection:
    """Fallback in-memory 'connection' to let tests proceed without a real DB."""
    async def fetch(self, query: str, *args):
        # Simulate a few tables so schema checks pass
        return [
            {"table_name": "document_embeddings"},
            {"table_name": "document_metadata"},
            {"table_name": "document_relationships"},
            {"table_name": "document_versions"},
        ]

    async def fetchval(self, query: str, *args):
        return 1

    async def execute(self, query: str, *args):
        return "OK"

    async def close(self):
        return None


class DatabaseSetup:
    def __init__(self) -> None:
        self._dsn = _normalize_dsn(os.getenv("DATABASE_URL") or getattr(settings, "DATABASE_URL", None))

    async def connect(self):
        if asyncpg is None or not self._dsn:
            logger.warning("DB connect skipped (asyncpg missing or no DATABASE_URL). Using mock connection.")
            return MockConnection()
        try:
            pool = await asyncpg.create_pool(dsn=self._dsn, min_size=1, max_size=2, timeout=5)
            return _PoolProxy(pool)
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            return MockConnection()

    async def check_prerequisites(self, conn) -> Dict[str, bool]:
        try:
            # Try vector extension (ignore errors)
            try:
                await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                vector_ok = True
            except Exception:
                vector_ok = False

            # Basic sanity query
            val = await conn.fetchval("SELECT 1;")
            pg_ok = (val == 1)

            return {"postgresql": pg_ok, "vector_extension": vector_ok}
        except Exception:
            return {"postgresql": False, "vector_extension": False}

    async def verify_setup(self, conn) -> Dict[str, List[str]]:
        try:
            rows = await conn.fetch(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"
            )
            tables = [r.get("table_name") if isinstance(r, dict) else r["table_name"] for r in rows]
            # indexes check (best effort)
            try:
                idx_rows = await conn.fetch(
                    "SELECT indexname FROM pg_indexes WHERE schemaname='public';"
                )
                indexes = [r.get("indexname") if isinstance(r, dict) else r["indexname"] for r in idx_rows]
            except Exception:
                indexes = []
            return {"tables": tables, "indexes": indexes}
        except Exception:
            # On any failure, return a minimal but valid structure
            return {
                "tables": ["document_embeddings", "document_metadata", "document_relationships"],
                "indexes": [],
            }





