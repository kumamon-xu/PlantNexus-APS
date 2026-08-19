"""Lazy SQLAlchemy connectivity for readiness and future repositories."""

from __future__ import annotations

import math
from dataclasses import dataclass

from pydantic import SecretStr
from sqlalchemy import Engine, create_engine, text


@dataclass
class DatabaseClient:
    """A lazily connecting engine wrapper.

    SQLAlchemy engine construction does not open a connection. ``probe`` is
    the first operation that may touch the network.
    """

    engine: Engine

    def probe(self) -> None:
        with self.engine.connect() as connection:
            value = connection.scalar(text("SELECT 1"))
        if value != 1:
            raise RuntimeError("database readiness probe returned an unexpected result")

    def close(self) -> None:
        self.engine.dispose()


def create_database_client(
    database_url: SecretStr,
    *,
    timeout_seconds: float,
) -> DatabaseClient:
    raw_url = database_url.get_secret_value()
    connect_args: dict[str, object] = {}
    if raw_url.startswith("postgresql+psycopg://"):
        connect_args["connect_timeout"] = max(1, math.ceil(timeout_seconds))
    engine = create_engine(
        raw_url,
        connect_args=connect_args,
        pool_pre_ping=True,
    )
    return DatabaseClient(engine=engine)


__all__ = ["DatabaseClient", "create_database_client"]
