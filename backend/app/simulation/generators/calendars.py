"""Pure deterministic resource-calendar source-record generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from app.domain.contracts import JsonValue
from app.simulation.generators.contracts import (
    GeneratedRecordCollections,
    GenerationContext,
    P1_GENERATOR_VERSION,
    SyntheticGeneratorError,
    SyntheticGeneratorErrorCode,
    require_p1_generator_context,
)
from app.simulation.generators.determinism import (
    SeedMaterial,
    format_synthetic_utc,
    synthetic_time_origin,
)


@dataclass(frozen=True, slots=True)
class DeterministicCalendarGenerator:
    """Create one UTC calendar for each generated unit-capacity resource."""

    @property
    def generator_version(self) -> str:
        return P1_GENERATOR_VERSION

    def generate_calendars(
        self,
        context: GenerationContext,
        records: GeneratedRecordCollections,
    ) -> GeneratedRecordCollections:
        profile, _, scale = require_p1_generator_context(context)
        resources = tuple(records.get("resources", ()))
        if len(resources) != scale.resource_count:
            raise SyntheticGeneratorError(
                SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                "calendar layer requires the complete generated resource collection",
            )
        seed_root = SeedMaterial(
            context.seed, context.generator_id, context.generator_version
        )
        seed = seed_root.child("calendars")
        origin = synthetic_time_origin(seed_root.child("timeline"))
        calendars: list[dict[str, JsonValue]] = []

        for resource_index, resource in enumerate(resources):
            if not isinstance(resource, dict) or not isinstance(
                resource.get("calendar_id"), str
            ):
                raise SyntheticGeneratorError(
                    SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                    "generated resource lacks its calendar identity",
                )
            calendar_id = resource["calendar_id"]
            intervals: list[JsonValue] = []
            for fragment_index in range(scale.calendar_fragmentation_count):
                pattern_position = seed.deterministic_index(
                    len(profile.calendar_pattern_ids),
                    "calendar-pattern",
                    index=(
                        resource_index * scale.calendar_fragmentation_count
                        + fragment_index
                    ),
                )
                jitter_minutes = 15 * seed.deterministic_integer(
                    0,
                    2,
                    "calendar-jitter-steps",
                    index=(
                        resource_index * scale.calendar_fragmentation_count
                        + fragment_index
                    ),
                )
                start = origin + timedelta(
                    hours=2 + fragment_index * 3,
                    minutes=resource_index * 5 + jitter_minutes,
                )
                end = start + timedelta(minutes=30)
                intervals.append(
                    {
                        "interval_id": (
                            f"calendar-interval-{resource_index + 1:03d}-"
                            f"{fragment_index + 1:03d}"
                        ),
                        "start_at": format_synthetic_utc(start),
                        "end_at": format_synthetic_utc(end),
                        "reason": profile.calendar_pattern_ids[pattern_position],
                    }
                )
            calendars.append(
                {
                    "calendar_id": calendar_id,
                    "timezone": "UTC",
                    "unavailable_intervals": intervals,
                }
            )

        return {**records, "calendars": tuple(calendars)}


__all__ = ["DeterministicCalendarGenerator"]
