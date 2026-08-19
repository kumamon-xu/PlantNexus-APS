"""Dependency-neutral liveness and sanitized readiness contracts."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

Probe = Callable[[], None]

_DEPENDENCY_CODES = {
    "database": "DATABASE_UNAVAILABLE",
    "redis": "REDIS_UNAVAILABLE",
}


@dataclass(frozen=True)
class HealthCheck:
    name: str
    status: str
    code: str | None = None

    def to_dict(self) -> dict[str, str]:
        result = {"name": self.name, "status": self.status}
        if self.code is not None:
            result["code"] = self.code
        return result


@dataclass(frozen=True)
class HealthReport:
    status: str
    service: str
    build: Mapping[str, str]
    checks: tuple[HealthCheck, ...]

    @property
    def ready(self) -> bool:
        return self.status == "UP"

    def to_dict(self) -> dict[str, object]:
        return {
            "contract": "health-report.v1",
            "status": self.status,
            "service": self.service,
            "build": dict(self.build),
            "checks": [check.to_dict() for check in self.checks],
        }


def liveness_report(*, service: str, build: Mapping[str, str]) -> HealthReport:
    return HealthReport(
        status="UP",
        service=service,
        build=build,
        checks=(HealthCheck(name="process", status="UP"),),
    )


def readiness_report(
    *,
    service: str,
    build: Mapping[str, str],
    probes: Mapping[str, Probe],
) -> HealthReport:
    checks: list[HealthCheck] = []
    for name, probe in probes.items():
        try:
            probe()
        except Exception:  # adapters may raise driver-specific errors; never expose them
            checks.append(
                HealthCheck(
                    name=name,
                    status="DOWN",
                    code=_DEPENDENCY_CODES.get(name, "DEPENDENCY_UNAVAILABLE"),
                )
            )
        else:
            checks.append(HealthCheck(name=name, status="UP"))
    overall = "UP" if all(check.status == "UP" for check in checks) else "DOWN"
    return HealthReport(
        status=overall,
        service=service,
        build=build,
        checks=tuple(checks),
    )


__all__ = [
    "HealthCheck",
    "HealthReport",
    "Probe",
    "liveness_report",
    "readiness_report",
]
