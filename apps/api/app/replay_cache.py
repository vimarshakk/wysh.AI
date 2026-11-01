"""Bounded in-memory replay protection for the isolated synthetic API lane."""

from __future__ import annotations

from collections import OrderedDict
from threading import Lock
from typing import Any


class ReplayCache:
    """Small LRU cache preventing unbounded idempotency-key retention."""

    def __init__(self, max_entries: int = 1024):
        if max_entries < 1:
            raise ValueError("max_entries must be positive")
        self.max_entries = max_entries
        self._entries: OrderedDict[str, Any] = OrderedDict()
        self._lock = Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            value = self._entries.get(key)
            if value is not None:
                self._entries.move_to_end(key)
            return value

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            self._entries[key] = value
            self._entries.move_to_end(key)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)
