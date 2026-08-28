"""TASK-P4-08 frozen public-contract and cross-artifact lineage tests."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from alembic import command
from alembic.config import Config
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from sqlalchemy import create_engine

from app.application.replan_application_check import (
    build_replan_application_fixture,
    seed_replan_application_runtime,
)
from app.domain.execution_contracts import require_p4_document


ROOT = Path(__file__).resolve().parents[3]


def _validator(name: str) -> Draft202012Validator:
    schemas: dict[str, dict[str, object]] = {}
    resources: list[tuple[str, Resource[object]]] = []
    for path in sorted((ROOT / "schemas/json").glob("*.json")):
        schema = cast(
            dict[str, object], json.loads(path.read_text(encoding="utf-8"))
        )
        schemas[path.name] = schema
        resources.append((cast(str, schema["$id"]), Resource.from_contents(schema)))
    return Draft202012Validator(
        schemas[name],
        registry=Registry().with_resources(resources),
        format_checker=FormatChecker(),
    )


def _configuration(database_url: str) -> Config:
    value = Config(str(ROOT / "alembic.ini"))
    value.set_main_option("script_location", str(ROOT / "backend/migrations"))
    value.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return value


def test_application_outputs_only_frozen_p4_contracts_and_exact_references() -> None:
    fixture = build_replan_application_fixture(ROOT)
    assert require_p4_document(fixture.request) == "replan-request.v1"
    _validator("replan-request.schema.json").validate(fixture.request)
    _validator("kpi.v2.schema.json").validate(fixture.before_kpi)
    _validator("kpi.v2.schema.json").validate(fixture.after_kpi)

    with TemporaryDirectory(prefix="plantnexus-p4-08-contract-") as directory:
        database_url = f"sqlite:///{(Path(directory) / 'contract.db').as_posix()}"
        configuration = _configuration(database_url)
        command.upgrade(configuration, "head")
        engine = create_engine(database_url)
        try:
            output = seed_replan_application_runtime(
                ROOT, engine, fixture
            ).service.execute(fixture.input, fixture.context)
        finally:
            engine.dispose()
            command.downgrade(configuration, "base")

    assert output.schedule_version is not None
    assert output.solver_report is not None
    assert output.change_report is not None
    assert require_p4_document(output.schedule_version) == "schedule-version.v2"
    assert require_p4_document(output.solver_report) == "solver-report.v2"
    assert require_p4_document(output.change_report) == "change-report.v1"
    _validator("schedule-version.v2.schema.json").validate(output.schedule_version)
    _validator("solver-report.v2.schema.json").validate(output.solver_report)
    _validator("change-report.schema.json").validate(output.change_report)

    result_schedule = cast(dict[str, object], output.result["new_schedule_version"])
    assert result_schedule == {
        "document_version": "schedule-version.v2",
        "artifact_id": output.schedule_version["schedule_version_id"],
        "fingerprint": output.schedule_version["content_fingerprint"],
    }
    assert output.change_report["new_schedule_version"] == {
        "schedule_version_version": "schedule-version.v2",
        "schedule_version_id": output.schedule_version["schedule_version_id"],
        "state": "DRAFT",
        "content_fingerprint": output.schedule_version["content_fingerprint"],
    }
    assert output.schedule_version["decision"] is None
    assert output.schedule_version["publication"] is None
    assert output.schedule_version["allowed_actions"] == [
        "view",
        "edit",
        "lock",
        "audit",
    ]
