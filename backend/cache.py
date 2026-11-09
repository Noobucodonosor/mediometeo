"""Cache SQLite con supporto TTL e Stale-While-Revalidate (ADR-0001, ADR-0002)."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class CacheEntry:
    """Voce recuperata dalla cache SQLite."""

    key: str
    payload: Any
    created_at: float
    expires_at: float

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    @property
    def age_seconds(self) -> int:
        return max(0, int(time.time() - self.created_at))


class SQLiteCache:
    """Gestore cache persistente su SQLite per resilienza anti-blackout."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS kv_cache (
                    cache_key TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_kv_category ON kv_cache(category)"
            )
            conn.commit()

    def set(
        self, key: str, payload: Any, ttl_seconds: int, category: str = "general"
    ) -> CacheEntry:
        now = time.time()
        expires_at = now + max(1, ttl_seconds)
        serialized = json.dumps(payload, ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO kv_cache (cache_key, category, payload_json, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    category = excluded.category,
                    payload_json = excluded.payload_json,
                    created_at = excluded.created_at,
                    expires_at = excluded.expires_at
                """,
                (key, category, serialized, now, expires_at),
            )
            conn.commit()
        return CacheEntry(key=key, payload=payload, created_at=now, expires_at=expires_at)

    def get(self, key: str, allow_stale: bool = False) -> CacheEntry | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT cache_key, payload_json, created_at, expires_at FROM kv_cache WHERE cache_key = ?",
                (key,),
            ).fetchone()
        if not row:
            return None
        entry = CacheEntry(
            key=row["cache_key"],
            payload=json.loads(row["payload_json"]),
            created_at=float(row["created_at"]),
            expires_at=float(row["expires_at"]),
        )
        if entry.is_expired and not allow_stale:
            return None
        return entry

    def stats(self) -> dict[str, Any]:
        now = time.time()
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) AS c FROM kv_cache").fetchone()["c"]
            fresh = conn.execute(
                "SELECT COUNT(*) AS c FROM kv_cache WHERE expires_at >= ?", (now,)
            ).fetchone()["c"]
        return {
            "total_entries": total,
            "fresh_entries": fresh,
            "stale_entries": max(0, total - fresh),
        }
