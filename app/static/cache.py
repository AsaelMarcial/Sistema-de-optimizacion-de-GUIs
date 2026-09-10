from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Lock
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    value: T
    expires_at: datetime


class ContextCache(Generic[T]):
    def _init_(self, timeout: timedelta):
        self.timeout = timeout
        self._data: dict[str, CacheEntry[T]] = {}
        self._lock = Lock()

    def set(self, key: str, value: T) -> None:
        entry = CacheEntry(
            value=value,
            expires_at=datetime.now() + self.timeout,
        )
        with self._lock:
            self._data[key] = entry

    def get(self, key: str) -> T | None:
        now = datetime.now()
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            if entry.expires_at <= now:
                del self._data[key]
                return None
            return entry.value

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)
