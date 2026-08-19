"""Environment-only configuration with fail-closed production guards."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Self

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, SettingsError

from app import CODE_VERSION, SCHEMA_VERSION, SPEC_VERSION

_COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")


class RuntimeEnvironment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    BENCHMARK = "benchmark"
    PRODUCTION = "production"


class DataPlane(StrEnum):
    DEVELOPMENT = "development"
    SIMULATION = "simulation"
    PRODUCTION = "production"


class ConfigurationError(RuntimeError):
    """Sanitized configuration failure safe to expose to an operator."""


class Settings(BaseSettings):
    """PlantNexus runtime settings.

    Values come from ``PLANTNEXUS_*`` environment variables or explicit test
    arguments. An ``.env`` file is deliberately never loaded implicitly.
    """

    model_config = SettingsConfigDict(
        env_prefix="PLANTNEXUS_",
        env_file=None,
        env_ignore_empty=True,
        case_sensitive=False,
        extra="forbid",
    )

    service_name: str = Field(default="plantnexus-aps", min_length=1, max_length=80)
    runtime_environment: RuntimeEnvironment = RuntimeEnvironment.DEVELOPMENT
    data_plane: DataPlane = DataPlane.DEVELOPMENT
    code_commit: str = "uncommitted"
    log_level: str = "INFO"
    otel_trace_context_enabled: bool = True
    simulation_api_enabled: bool = False

    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://plantnexus@localhost:5432/plantnexus_dev"
    )
    redis_url: SecretStr = SecretStr("redis://localhost:6379/0")
    celery_broker_url: SecretStr = SecretStr("redis://localhost:6379/1")
    celery_result_backend_url: SecretStr = SecretStr("redis://localhost:6379/2")

    readiness_timeout_seconds: float = Field(default=2.0, ge=0.1, le=30.0)
    job_heartbeat_seconds: int = Field(default=30, ge=1, le=3600)
    job_lease_seconds: int = Field(default=120, ge=2, le=86400)

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if not raw.startswith(("postgresql+psycopg://", "sqlite://")):
            raise ValueError("database_url must use postgresql+psycopg or sqlite")
        return value

    @field_validator("redis_url", "celery_broker_url", "celery_result_backend_url")
    @classmethod
    def validate_redis_url(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith(("redis://", "rediss://")):
            raise ValueError("Redis endpoints must use redis or rediss")
        return value

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("unsupported log level")
        return normalized

    @model_validator(mode="after")
    def enforce_environment_guards(self) -> Self:
        if self.job_lease_seconds <= self.job_heartbeat_seconds:
            raise ValueError("job lease must be longer than heartbeat interval")

        is_production_runtime = self.runtime_environment is RuntimeEnvironment.PRODUCTION
        is_production_data = self.data_plane is DataPlane.PRODUCTION
        if is_production_runtime != is_production_data:
            raise ValueError("production runtime and production data plane must match")
        if is_production_data and self.simulation_api_enabled:
            raise ValueError("simulation API is forbidden on the production data plane")
        if is_production_runtime:
            database_url = self.database_url.get_secret_value()
            if not database_url.startswith("postgresql+psycopg://"):
                raise ValueError("production requires PostgreSQL")
            if _COMMIT_PATTERN.fullmatch(self.code_commit) is None:
                raise ValueError("production requires an immutable 40-character code commit")
        elif self.code_commit != "uncommitted" and _COMMIT_PATTERN.fullmatch(self.code_commit) is None:
            raise ValueError("code_commit must be 'uncommitted' or a 40-character commit")
        return self

    def build_metadata(self) -> dict[str, str]:
        """Return public build metadata; no configuration secret is included."""

        return {
            "code_version": CODE_VERSION,
            "spec_version": SPEC_VERSION,
            "schema_version": SCHEMA_VERSION,
            "code_commit": self.code_commit,
        }

    def safe_summary(self) -> dict[str, str | bool]:
        """Return an operator-safe summary without endpoint values."""

        return {
            "service_name": self.service_name,
            "runtime_environment": self.runtime_environment.value,
            "data_plane": self.data_plane.value,
            "simulation_api_enabled": self.simulation_api_enabled,
            "code_commit": self.code_commit,
        }


def load_settings() -> Settings:
    """Load environment settings and replace Pydantic detail with a safe error."""

    try:
        return Settings()
    except (SettingsError, ValidationError):
        raise ConfigurationError("invalid PLANTNEXUS_ configuration") from None


__all__ = [
    "ConfigurationError",
    "DataPlane",
    "RuntimeEnvironment",
    "Settings",
    "load_settings",
]
