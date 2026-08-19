"""Lazy Redis connectivity for readiness and the Celery adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from pydantic import SecretStr
from redis import Redis


@dataclass
class RedisClient:
    client: Redis

    def probe(self) -> None:
        if self.client.ping() is not True:
            raise RuntimeError("Redis readiness probe returned an unexpected result")

    def close(self) -> None:
        self.client.close()


def create_redis_client(redis_url: SecretStr, *, timeout_seconds: float) -> RedisClient:
    client = cast(
        Redis,
        Redis.from_url(
            redis_url.get_secret_value(),
            socket_connect_timeout=timeout_seconds,
            socket_timeout=timeout_seconds,
            decode_responses=True,
        ),
    )
    return RedisClient(client=client)


__all__ = ["RedisClient", "create_redis_client"]
