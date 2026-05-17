from __future__ import annotations

from datetime import UTC, datetime, timedelta


class TTLCache:
    def __init__(self, ttl_seconds: int = 120) -> None:
        self.ttl = ttl_seconds
        self._store: dict[str, tuple[datetime, object]] = {}
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> object | None:
        item = self._store.get(key)
        if item is None:
            self.misses += 1
            return None
        expires_at, value = item
        if expires_at < datetime.now(UTC):
            self._store.pop(key, None)
            self.misses += 1
            return None
        self.hits += 1
        return value

    def set(self, key: str, value: object) -> None:
        self._store[key] = (datetime.now(UTC) + timedelta(seconds=self.ttl), value)

    def stats(self) -> dict[str, int]:
        return {"hits": self.hits, "misses": self.misses, "entries": len(self._store)}
