"""Pure P3 ScheduleVersion and ExportJob persistence-state contracts."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import cast

import pytest

from app.domain.state_machines.export_job import (
    ExportJobLeaseError,
    ExportJobPersistenceTransitionError,
    require_export_job_heartbeat,
    require_export_job_transition,
)
from app.domain.state_machines.schedule_version import (
    ScheduleVersionPersistenceTransitionError,
    require_schedule_version_transition,
)

ROOT = Path(__file__).resolve().parents[3]


def _sample(name: str) -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads((ROOT / "schemas" / "samples" / name).read_text(encoding="utf-8")),
    )


def test_schedule_transition_preserves_immutable_version_content() -> None:
    draft = _sample("schedule-version.v1.synthetic.json")
    ready = deepcopy(draft)
    ready["state"] = "READY_FOR_REVIEW"
    ready["allowed_actions"] = ["view", "approve", "reject"]
    assert require_schedule_version_transition(draft, ready) == (
        "DRAFT",
        "READY_FOR_REVIEW",
    )

    changed = deepcopy(ready)
    changed["revision"] = 2
    with pytest.raises(ScheduleVersionPersistenceTransitionError):
        require_schedule_version_transition(draft, changed)
    with pytest.raises(ScheduleVersionPersistenceTransitionError):
        require_schedule_version_transition(draft, draft)


def test_export_transition_attempt_and_lease_contract() -> None:
    created = _sample("export-job.v1.synthetic.json")
    exporting = deepcopy(created)
    exporting.update(
        {
            "state": "EXPORTING",
            "attempt": 1,
            "lease_reference": f"sha256:{'f' * 64}",
            "heartbeat_at_utc": "2026-08-24T01:10:00Z",
            "started_at_utc": "2026-08-24T01:10:00Z",
            "updated_at_utc": "2026-08-24T01:10:00Z",
        }
    )
    expiry = datetime(2026, 8, 24, 1, 15, tzinfo=UTC)
    assert require_export_job_transition(
        created,
        exporting,
        lease_expires_at_utc=expiry,
    ) == ("CREATED", "EXPORTING")

    wrong_attempt = deepcopy(exporting)
    wrong_attempt["attempt"] = 2
    with pytest.raises(ExportJobPersistenceTransitionError):
        require_export_job_transition(
            created,
            wrong_attempt,
            lease_expires_at_utc=expiry,
        )
    with pytest.raises(ExportJobLeaseError):
        require_export_job_transition(
            created,
            exporting,
            lease_expires_at_utc=None,
        )


def test_export_heartbeat_is_not_a_state_self_transition() -> None:
    exporting = _sample("export-job.v1.synthetic.json")
    exporting.update(
        {
            "state": "EXPORTING",
            "attempt": 1,
            "lease_reference": f"sha256:{'f' * 64}",
            "heartbeat_at_utc": "2026-08-24T01:10:00Z",
            "started_at_utc": "2026-08-24T01:10:00Z",
            "updated_at_utc": "2026-08-24T01:10:00Z",
        }
    )
    heartbeat = deepcopy(exporting)
    heartbeat["heartbeat_at_utc"] = "2026-08-24T01:11:00Z"
    heartbeat["updated_at_utc"] = "2026-08-24T01:11:00Z"
    require_export_job_heartbeat(
        exporting,
        heartbeat,
        expected_lease_reference=f"sha256:{'f' * 64}",
        stored_lease_expires_at_utc=datetime(2026, 8, 24, 1, 15, tzinfo=UTC),
        observed_at_utc=datetime(2026, 8, 24, 1, 11, tzinfo=UTC),
        new_lease_expires_at_utc=datetime(2026, 8, 24, 1, 16, tzinfo=UTC),
    )
    with pytest.raises(ExportJobLeaseError):
        require_export_job_heartbeat(
            exporting,
            heartbeat,
            expected_lease_reference=f"sha256:{'e' * 64}",
            stored_lease_expires_at_utc=datetime(2026, 8, 24, 1, 15, tzinfo=UTC),
            observed_at_utc=datetime(2026, 8, 24, 1, 11, tzinfo=UTC),
            new_lease_expires_at_utc=datetime(2026, 8, 24, 1, 16, tzinfo=UTC),
        )
