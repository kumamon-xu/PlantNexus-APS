"""Idempotency protocol plus an explicit process-local reference store."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import RLock
from typing import Protocol

_SHA256 = re.compile(r"[0-9a-f]{64}")


class IdempotencyConflictError(ValueError):
    pass


@dataclass(frozen=True)
class IdempotencyRecord:
    scope: str
    key: str
    request_fingerprint: str
    logical_id: str
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.scope or not self.key or not self.logical_id:
            raise ValueError("scope, key, and logical_id must not be empty")
        if _SHA256.fullmatch(self.request_fingerprint) is None:
            raise ValueError("request_fingerprint must be a lowercase SHA-256 hex digest")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() != timedelta(0):
            raise ValueError("created_at must be timezone-aware UTC")


class IdempotencyStore(Protocol):
    def register(
        self,
        *,
        scope: str,
        key: str,
        request_fingerprint: str,
        logical_id: str,
        now: datetime,
    ) -> IdempotencyRecord: ...


class InMemoryIdempotencyStore:
    """Thread-safe reference semantics, not a durable distributed store."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str], IdempotencyRecord] = {}
        self._lock = RLock()

    def register(
        self,
        *,
        scope: str,
        key: str,
        request_fingerprint: str,
        logical_id: str,
        now: datetime,
    ) -> IdempotencyRecord:
        candidate = IdempotencyRecord(
            scope=scope,
            key=key,
            request_fingerprint=request_fingerprint,
            logical_id=logical_id,
            created_at=now,
        )
        identity = (scope, key)
        with self._lock:
            existing = self._records.get(identity)
            if existing is None:
                self._records[identity] = candidate
                return candidate
            if existing.request_fingerprint != request_fingerprint:
                raise IdempotencyConflictError(
                    "idempotency key was reused with a different request fingerprint"
                )
            return existing

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)


__all__ = [
    "IdempotencyConflictError",
    "IdempotencyRecord",
    "IdempotencyStore",
    "InMemoryIdempotencyStore",
]
