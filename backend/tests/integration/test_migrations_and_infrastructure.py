"""TASK-P0-08 migration, lazy connectivity, Celery, and report evidence."""

from __future__ import annotations

import json
from pathlib import Path

from alembic import command
from alembic.config import Config
from celery import Celery
from pydantic import SecretStr
from sqlalchemy import create_engine, inspect

from app.infrastructure.config import RuntimeEnvironment, Settings
from app.infrastructure.contract_check import main as engineering_check_main
from app.infrastructure.database import create_database_client
from app.infrastructure.redis_client import create_redis_client
from app.jobs.celery_app import create_celery_app

ROOT = Path(__file__).resolve().parents[3]


def _alembic_config(database_url: str) -> Config:
    configuration = Config(str(ROOT / "alembic.ini"))
    configuration.set_main_option(
        "script_location",
        str(ROOT / "backend" / "migrations"),
    )
    configuration.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return configuration


def test_empty_database_migration_upgrades_and_downgrades(tmp_path: Path) -> None:
    database_path = tmp_path / "engineering.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    configuration = _alembic_config(database_url)

    command.upgrade(configuration, "head")
    engine = create_engine(database_url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert {
            "alembic_version",
            "engineering_idempotency_records",
            "engineering_job_records",
        } <= tables
        unique_constraints = inspect(engine).get_unique_constraints(
            "engineering_idempotency_records"
        )
        assert {constraint["name"] for constraint in unique_constraints} == {
            "uq_engineering_idempotency_scope_key"
        }
    finally:
        engine.dispose()

    command.downgrade(configuration, "base")
    engine = create_engine(database_url)
    try:
        tables_after = set(inspect(engine).get_table_names())
        assert "engineering_job_records" not in tables_after
        assert "engineering_idempotency_records" not in tables_after
    finally:
        engine.dispose()


def test_database_engine_does_not_connect_until_probe(tmp_path: Path) -> None:
    database_path = tmp_path / "lazy.db"
    client = create_database_client(
        SecretStr(f"sqlite:///{database_path.as_posix()}"),
        timeout_seconds=1,
    )
    assert not database_path.exists()
    client.probe()
    assert database_path.exists()
    client.close()


def test_redis_client_does_not_connect_during_construction() -> None:
    client = create_redis_client(
        SecretStr("redis://127.0.0.1:1/0"),
        timeout_seconds=0.1,
    )
    client.close()


def test_celery_adapter_is_json_only_and_registers_no_business_tasks() -> None:
    application = create_celery_app(
        Settings(runtime_environment=RuntimeEnvironment.TEST)
    )
    assert isinstance(application, Celery)
    assert application.conf.accept_content == ["json"]
    assert application.conf.task_serializer == "json"
    assert application.conf.result_serializer == "json"
    assert application.conf.task_acks_late is True
    assert application.conf.task_reject_on_worker_lost is True
    assert application.conf.worker_prefetch_multiplier == 1
    custom_tasks = {
        task_name
        for task_name in application.tasks
        if not task_name.startswith("celery.")
    }
    assert custom_tasks == set()


def test_engineering_contract_check_writes_machine_report(tmp_path: Path) -> None:
    report_path = tmp_path / "engineering.json"
    exit_code = engineering_check_main(
        ["--root", str(ROOT), "--report", str(report_path)]
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert report["report_version"] == "engineering-skeleton-report.v1"
    assert report["status"] == "PASS"
    assert report["check_count"] == 6
    assert report["boundaries"]["solver"] == "NOT_INSTALLED"
