"""Replay TASK-P5-01 evidence and emit the bounded portfolio decision report."""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

import yaml


type JsonObject = dict[str, Any]

REPORT_VERSION = "p5-capability-qualification-report.v1"
PROFILE_VERSION = "p5-capability-qualification-profile.v1"
MANIFEST_VERSION = "p5-capability-evidence-manifest.v1"
RECORD_VERSION = "p5-capability-evidence-record.v1"
TASK_ID = "TASK-P5-01"
DIFF_BASE = "4ccb2ed99ffe73abeb0462efff4a5342cd7c5522"
IMPACT_RULES = (
    "IMPACT-BENCHMARK",
    "IMPACT-DOCS",
    "IMPACT-FIXTURE",
    "IMPACT-TESTS",
)
REQUIRED_FACTS = (
    "source_is_qualified",
    "source_replay_verified",
    "current_approximation_unacceptable",
    "candidate_specific_gate_passed",
    "policy_inputs_defined",
)
METRICS = ("runtime", "memory", "model_size", "quality")
SOURCE_FIELDS = (
    ("real_requirement", "REAL_REQUIREMENT"),
    ("simulation", "VERSIONED_SIMULATION"),
    ("benchmark", "VERSIONED_BENCHMARK"),
)
EXPECTED_CANDIDATES = (
    "P5-CANDIDATE-SECONDARY-RESOURCE",
    "P5-CANDIDATE-SEQUENCE-SETUP",
    "P5-CANDIDATE-MATERIAL-COMPETITION",
    "P5-CANDIDATE-BATCH",
    "P5-CANDIDATE-SPLIT-MERGE",
    "P5-CANDIDATE-BUFFER",
    "P5-CANDIDATE-PREEMPTION",
    "P5-CANDIDATE-DECOMPOSITION",
    "P5-CANDIDATE-ROLLING-HORIZON",
)
CONSTRAINT_CANDIDATES = {
    "P5-CANDIDATE-SECONDARY-RESOURCE": ("SECONDARY_CAPACITY", "C-012"),
    "P5-CANDIDATE-SEQUENCE-SETUP": ("SEQUENCE_DEPENDENT_SETUP", "C-013"),
    "P5-CANDIDATE-MATERIAL-COMPETITION": ("MATERIAL_COMPETITION", "C-014"),
    "P5-CANDIDATE-BATCH": ("BATCH_PROCESSING", "C-015"),
    "P5-CANDIDATE-SPLIT-MERGE": ("SPLIT_MERGE", "C-016"),
    "P5-CANDIDATE-BUFFER": ("BUFFER_CAPACITY", "C-017"),
    "P5-CANDIDATE-PREEMPTION": ("PREEMPTIVE_OPERATION", "C-018"),
}


class QualificationError(ValueError):
    """A fail-closed qualification evidence error."""

    def __init__(self, code: str, field: str, message: str) -> None:
        super().__init__(f"{code} at {field}: {message}")
        self.code = code
        self.field = field
        self.message = message


@dataclass(frozen=True, slots=True)
class QualificationBundle:
    profile: JsonObject
    manifest: JsonObject
    records: tuple[JsonObject, ...]
    manifest_fingerprint: str
    verified_asset_count: int


def _mapping(value: object, field: str) -> JsonObject:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise QualificationError("INVALID_EVIDENCE", field, "must be an object")
    return cast(JsonObject, value)


def _array(value: object, field: str) -> list[object]:
    if not isinstance(value, list):
        raise QualificationError("INVALID_EVIDENCE", field, "must be an array")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise QualificationError("INVALID_EVIDENCE", field, "must be non-empty text")
    return value


def _boolean(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise QualificationError("INVALID_EVIDENCE", field, "must be boolean")
    return value


def _exact_keys(value: Mapping[str, object], expected: set[str], field: str) -> None:
    actual = set(value)
    if actual != expected:
        raise QualificationError(
            "INVALID_EVIDENCE",
            field,
            f"keys must be {sorted(expected)}; observed {sorted(actual)}",
        )


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_fingerprint(value: object) -> str:
    return f"sha256:{hashlib.sha256(_canonical_bytes(value)).hexdigest()}"


def _file_fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _rooted_file(root: Path, relative: str, field: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise QualificationError(
            "INVALID_EVIDENCE_PATH", field, "must remain inside repository root"
        ) from error
    if not candidate.is_file() or candidate.is_symlink():
        raise QualificationError(
            "INVALID_EVIDENCE_PATH", field, "must be a regular non-symlink file"
        )
    return candidate


def _read_json(path: Path, field: str) -> JsonObject:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise QualificationError(
            "INVALID_EVIDENCE_JSON", field, f"invalid JSON: {error.msg}"
        ) from error
    return _mapping(value, field)


def _verify_asset(root: Path, entry: Mapping[str, object], field: str) -> Path:
    _exact_keys(entry, {"path", "sha256"}, field)
    relative = _text(entry["path"], f"{field}.path")
    expected = _text(entry["sha256"], f"{field}.sha256")
    path = _rooted_file(root, relative, f"{field}.path")
    actual = _file_fingerprint(path)
    if actual != expected:
        raise QualificationError(
            "EVIDENCE_HASH_MISMATCH",
            field,
            f"expected {expected}; observed {actual}",
        )
    return path


def _validate_profile(profile: JsonObject) -> None:
    if profile.get("profile_version") != PROFILE_VERSION:
        raise QualificationError(
            "UNKNOWN_PROFILE",
            "profile.profile_version",
            f"must equal {PROFILE_VERSION}",
        )
    if profile.get("task_id") != TASK_ID or profile.get("diff_base") != DIFF_BASE:
        raise QualificationError(
            "PROFILE_IDENTITY_MISMATCH",
            "profile",
            "task_id and diff_base must match TASK-P5-01 activation",
        )
    if profile.get("data_plane") != "SIMULATION_DEVELOPMENT_ONLY":
        raise QualificationError(
            "DATA_PLANE_VIOLATION",
            "profile.data_plane",
            "Production-shaped evidence is prohibited",
        )
    if profile.get("decision_values") != ["SELECTED", "DEFERRED"]:
        raise QualificationError(
            "UNKNOWN_DECISION",
            "profile.decision_values",
            "must be the exact ordered decision enum",
        )
    if profile.get("source_types") != [
        "REAL_REQUIREMENT",
        "VERSIONED_SIMULATION",
        "VERSIONED_BENCHMARK",
    ]:
        raise QualificationError(
            "SOURCE_ISOLATION_VIOLATION",
            "profile.source_types",
            "must preserve the three source planes",
        )
    rule = _mapping(profile.get("selection_rule"), "profile.selection_rule")
    _exact_keys(
        rule,
        {
            "operator",
            "required_facts",
            "on_missing_or_false",
            "on_unknown_profile_or_tamper",
            "self_authored_need_is_qualified",
        },
        "profile.selection_rule",
    )
    if (
        rule["operator"] != "ALL_TRUE"
        or rule["required_facts"] != list(REQUIRED_FACTS)
        or rule["on_missing_or_false"] != "DEFERRED"
        or rule["on_unknown_profile_or_tamper"] != "TASK_FAIL"
        or rule["self_authored_need_is_qualified"] is not False
    ):
        raise QualificationError(
            "UNSAFE_SELECTION_RULE",
            "profile.selection_rule",
            "selection must fail closed and reject self-authored need",
        )
    if profile.get("metrics_required") != list(METRICS):
        raise QualificationError(
            "METRIC_CONTRACT_MISMATCH",
            "profile.metrics_required",
            "runtime/memory/model_size/quality are required",
        )
    if profile.get("benchmark_profiles") != ["xs", "s", "m"]:
        raise QualificationError(
            "BENCHMARK_SCOPE_MISMATCH",
            "profile.benchmark_profiles",
            "only the approved XS/S/M set is allowed",
        )
    candidates = _array(profile.get("candidates"), "profile.candidates")
    candidate_ids = [
        _text(_mapping(item, f"profile.candidates[{index}]").get("candidate_id"), f"profile.candidates[{index}].candidate_id")
        for index, item in enumerate(candidates)
    ]
    if tuple(candidate_ids) != EXPECTED_CANDIDATES:
        raise QualificationError(
            "CANDIDATE_SET_MISMATCH",
            "profile.candidates",
            "must contain the nine P5 candidates in stable order",
        )
    excluded = {_text(value, "profile.excluded[]") for value in _array(profile.get("excluded"), "profile.excluded")}
    required_exclusions = {
        "MULTI_FACTORY",
        "ALTERNATIVE_ROUTING_EXPANSION",
        "TOOLS_FIXTURES_SPECIALIZED_SEMANTICS",
        "HYBRID_STRATEGY",
        "AI_DURATION_PREDICTION",
        "P6_PLUS",
        "PRODUCTION_AUTHORITY_EXTERNAL_DEPLOYMENT_CAPACITY_SLA",
    }
    if excluded != required_exclusions:
        raise QualificationError(
            "P5_BOUNDARY_MISMATCH",
            "profile.excluded",
            "must preserve the exact P5/P6/Production exclusions",
        )


def _validate_source(
    value: object, *, field: str, expected_source_type: str
) -> JsonObject:
    source = _mapping(value, field)
    _exact_keys(
        source,
        {"source_type", "status", "qualified", "replayable", "source_ids"},
        field,
    )
    if source["source_type"] != expected_source_type:
        raise QualificationError(
            "SOURCE_ISOLATION_VIOLATION",
            f"{field}.source_type",
            f"must equal {expected_source_type}",
        )
    _text(source["status"], f"{field}.status")
    _boolean(source["qualified"], f"{field}.qualified")
    _boolean(source["replayable"], f"{field}.replayable")
    source_ids = [
        _text(item, f"{field}.source_ids[]")
        for item in _array(source["source_ids"], f"{field}.source_ids")
    ]
    if expected_source_type == "REAL_REQUIREMENT" and source_ids:
        raise QualificationError(
            "SOURCE_ISOLATION_VIOLATION",
            f"{field}.source_ids",
            "no real requirement IDs were supplied",
        )
    if expected_source_type == "VERSIONED_SIMULATION" and any(
        not item.startswith("SIM-ASSUMPTION-") for item in source_ids
    ):
        raise QualificationError(
            "SOURCE_ISOLATION_VIOLATION",
            f"{field}.source_ids",
            "Simulation sources must use registered SIM IDs",
        )
    if expected_source_type == "VERSIONED_BENCHMARK" and any(
        not item.startswith("P2-BENCHMARK-") for item in source_ids
    ):
        raise QualificationError(
            "SOURCE_ISOLATION_VIOLATION",
            f"{field}.source_ids",
            "Benchmark sources must use versioned P2 profile IDs",
        )
    return source


def validate_record(record: JsonObject, expected_candidate_id: str) -> None:
    if record.get("record_version") != RECORD_VERSION:
        raise QualificationError(
            "UNKNOWN_RECORD_VERSION",
            f"records.{expected_candidate_id}.record_version",
            f"must equal {RECORD_VERSION}",
        )
    if record.get("candidate_id") != expected_candidate_id:
        raise QualificationError(
            "CANDIDATE_ID_MISMATCH",
            f"records.{expected_candidate_id}.candidate_id",
            "manifest and record identity differ",
        )
    kind = _text(record.get("kind"), f"records.{expected_candidate_id}.kind")
    if kind not in {"CONSTRAINT", "STRATEGY"}:
        raise QualificationError(
            "UNKNOWN_CANDIDATE_KIND",
            f"records.{expected_candidate_id}.kind",
            "must be CONSTRAINT or STRATEGY",
        )
    _text(record.get("title"), f"records.{expected_candidate_id}.title")
    _text(
        record.get("necessity_question"),
        f"records.{expected_candidate_id}.necessity_question",
    )
    owner_tasks = [
        _text(item, f"records.{expected_candidate_id}.owner_tasks[]")
        for item in _array(
            record.get("owner_tasks"), f"records.{expected_candidate_id}.owner_tasks"
        )
    ]
    if len(owner_tasks) != 2 or any(not item.startswith("TASK-P5-") for item in owner_tasks):
        raise QualificationError(
            "OWNER_TASK_MISMATCH",
            f"records.{expected_candidate_id}.owner_tasks",
            "must identify one independent two-Task P5 chain",
        )
    if expected_candidate_id in CONSTRAINT_CANDIDATES:
        capability, constraint_id = CONSTRAINT_CANDIDATES[expected_candidate_id]
        if (
            kind != "CONSTRAINT"
            or record.get("capability_key") != capability
            or record.get("constraint_id") != constraint_id
        ):
            raise QualificationError(
                "CONSTRAINT_MAPPING_MISMATCH",
                f"records.{expected_candidate_id}",
                "capability/C-ID mapping differs from the frozen registry",
            )
    elif (
        kind != "STRATEGY"
        or record.get("capability_key") is not None
        or record.get("constraint_id") is not None
    ):
        raise QualificationError(
            "STRATEGY_MAPPING_MISMATCH",
            f"records.{expected_candidate_id}",
            "strategy candidates must not invent a capability key or C-ID",
        )

    evidence = _mapping(record.get("evidence"), f"records.{expected_candidate_id}.evidence")
    _exact_keys(evidence, {name for name, _ in SOURCE_FIELDS}, f"records.{expected_candidate_id}.evidence")
    validated_sources: dict[str, JsonObject] = {}
    for source_name, source_type in SOURCE_FIELDS:
        validated_sources[source_name] = _validate_source(
            evidence[source_name],
            field=f"records.{expected_candidate_id}.evidence.{source_name}",
            expected_source_type=source_type,
        )

    facts = _mapping(
        record.get("selection_facts"),
        f"records.{expected_candidate_id}.selection_facts",
    )
    _exact_keys(facts, set(REQUIRED_FACTS), f"records.{expected_candidate_id}.selection_facts")
    for name in REQUIRED_FACTS:
        _boolean(facts[name], f"records.{expected_candidate_id}.selection_facts.{name}")
    source_is_qualified = any(
        source["qualified"] is True for source in validated_sources.values()
    )
    if facts["source_is_qualified"] is not source_is_qualified:
        raise QualificationError(
            "SOURCE_FACT_MISMATCH",
            f"records.{expected_candidate_id}.selection_facts.source_is_qualified",
            "must equal the qualified state of the isolated evidence sources",
        )
    referenced_sources = [
        source
        for source in validated_sources.values()
        if cast(list[object], source["source_ids"])
    ]
    source_replay_verified = bool(referenced_sources) and all(
        source["replayable"] is True for source in referenced_sources
    )
    if facts["source_replay_verified"] is not source_replay_verified:
        raise QualificationError(
            "SOURCE_FACT_MISMATCH",
            f"records.{expected_candidate_id}.selection_facts.source_replay_verified",
            "must equal replayability of every referenced evidence source",
        )
    _text(
        record.get("candidate_specific_gate"),
        f"records.{expected_candidate_id}.candidate_specific_gate",
    )
    _text(
        record.get("current_boundary"),
        f"records.{expected_candidate_id}.current_boundary",
    )
    metrics = _mapping(record.get("metrics"), f"records.{expected_candidate_id}.metrics")
    _exact_keys(metrics, set(METRICS), f"records.{expected_candidate_id}.metrics")
    for metric in METRICS:
        _text(metrics[metric], f"records.{expected_candidate_id}.metrics.{metric}")
    open_dependencies = [
        _text(item, f"records.{expected_candidate_id}.open_dependencies[]")
        for item in _array(
            record.get("open_dependencies"),
            f"records.{expected_candidate_id}.open_dependencies",
        )
    ]
    if not open_dependencies or any(not item.startswith("OPEN-") for item in open_dependencies):
        raise QualificationError(
            "OPEN_BOUNDARY_MISMATCH",
            f"records.{expected_candidate_id}.open_dependencies",
            "each candidate must retain explicit PROD_OPEN dependencies",
        )
    gaps = [
        _text(item, f"records.{expected_candidate_id}.evidence_gaps[]")
        for item in _array(
            record.get("evidence_gaps"),
            f"records.{expected_candidate_id}.evidence_gaps",
        )
    ]
    if not gaps:
        raise QualificationError(
            "MISSING_DEFER_REASON",
            f"records.{expected_candidate_id}.evidence_gaps",
            "missing evidence must be recorded",
        )
    if record.get("expected_decision") not in {"SELECTED", "DEFERRED"}:
        raise QualificationError(
            "UNKNOWN_DECISION",
            f"records.{expected_candidate_id}.expected_decision",
            "must be SELECTED or DEFERRED",
        )
    _text(
        record.get("production_boundary"),
        f"records.{expected_candidate_id}.production_boundary",
    )


def decide_record(record: Mapping[str, object], profile: Mapping[str, object]) -> JsonObject:
    _validate_profile(dict(profile))
    candidate_id = _text(record.get("candidate_id"), "record.candidate_id")
    validate_record(dict(record), candidate_id)
    facts = _mapping(record.get("selection_facts"), f"records.{candidate_id}.selection_facts")
    failed_facts = [name for name in REQUIRED_FACTS if facts[name] is not True]
    decision = "SELECTED" if not failed_facts else "DEFERRED"
    expected = _text(record.get("expected_decision"), f"records.{candidate_id}.expected_decision")
    if decision != expected:
        raise QualificationError(
            "DECISION_EXPECTATION_MISMATCH",
            f"records.{candidate_id}.expected_decision",
            f"computed {decision}; declared {expected}",
        )
    evidence = _mapping(record.get("evidence"), f"records.{candidate_id}.evidence")
    source_summary = {
        name: {
            "status": _mapping(evidence[name], f"records.{candidate_id}.evidence.{name}")["status"],
            "qualified": _mapping(evidence[name], f"records.{candidate_id}.evidence.{name}")["qualified"],
            "replayable": _mapping(evidence[name], f"records.{candidate_id}.evidence.{name}")["replayable"],
            "source_ids": _mapping(evidence[name], f"records.{candidate_id}.evidence.{name}")["source_ids"],
        }
        for name, _ in SOURCE_FIELDS
    }
    projection: JsonObject = {
        "decision_record_version": "p5-capability-decision-record.v1",
        "candidate_id": candidate_id,
        "title": record["title"],
        "kind": record["kind"],
        "capability_key": record["capability_key"],
        "constraint_id": record["constraint_id"],
        "owner_tasks": record["owner_tasks"],
        "decision": decision,
        "failed_selection_facts": failed_facts,
        "selection_facts": dict(facts),
        "candidate_specific_gate": record["candidate_specific_gate"],
        "source_summary": source_summary,
        "current_boundary": record["current_boundary"],
        "metrics": record["metrics"],
        "open_dependencies": record["open_dependencies"],
        "evidence_gaps": record["evidence_gaps"],
        "production_boundary": record["production_boundary"],
    }
    projection["decision_fingerprint"] = canonical_fingerprint(projection)
    return projection


def load_qualification_bundle(
    root: Path,
    *,
    manifest_path: str = "fixtures/simulation/p5/qualification/evidence-manifest.v1.json",
) -> QualificationBundle:
    root = root.resolve()
    manifest_file = _rooted_file(root, manifest_path, "manifest_path")
    manifest = _read_json(manifest_file, "manifest")
    if manifest.get("manifest_version") != MANIFEST_VERSION:
        raise QualificationError(
            "UNKNOWN_MANIFEST_VERSION",
            "manifest.manifest_version",
            f"must equal {MANIFEST_VERSION}",
        )
    if manifest.get("task_id") != TASK_ID or manifest.get("diff_base") != DIFF_BASE:
        raise QualificationError(
            "MANIFEST_IDENTITY_MISMATCH",
            "manifest",
            "task_id and diff_base must match activation",
        )
    profile_entry = _mapping(manifest.get("profile"), "manifest.profile")
    profile_path = _verify_asset(root, profile_entry, "manifest.profile")
    profile = _read_json(profile_path, "profile")
    _validate_profile(profile)

    profile_candidates = {
        _text(_mapping(item, f"profile.candidates[{index}]").get("candidate_id"), f"profile.candidates[{index}].candidate_id"):
        _text(_mapping(item, f"profile.candidates[{index}]").get("record_path"), f"profile.candidates[{index}].record_path")
        for index, item in enumerate(_array(profile["candidates"], "profile.candidates"))
    }
    manifest_candidates = _array(
        manifest.get("candidate_records"), "manifest.candidate_records"
    )
    records: list[JsonObject] = []
    observed_ids: list[str] = []
    for index, raw_entry in enumerate(manifest_candidates):
        entry = _mapping(raw_entry, f"manifest.candidate_records[{index}]")
        _exact_keys(
            entry,
            {"candidate_id", "path", "sha256"},
            f"manifest.candidate_records[{index}]",
        )
        candidate_id = _text(
            entry["candidate_id"], f"manifest.candidate_records[{index}].candidate_id"
        )
        observed_ids.append(candidate_id)
        if profile_candidates.get(candidate_id) != entry["path"]:
            raise QualificationError(
                "CANDIDATE_PATH_MISMATCH",
                f"manifest.candidate_records[{index}].path",
                "profile and manifest path differ",
            )
        path = _verify_asset(
            root,
            {"path": entry["path"], "sha256": entry["sha256"]},
            f"manifest.candidate_records[{index}]",
        )
        record = _read_json(path, f"records.{candidate_id}")
        validate_record(record, candidate_id)
        records.append(record)
    if tuple(observed_ids) != EXPECTED_CANDIDATES:
        raise QualificationError(
            "CANDIDATE_SET_MISMATCH",
            "manifest.candidate_records",
            "must contain exactly the stable nine-candidate portfolio",
        )

    source_assets = _array(manifest.get("source_assets"), "manifest.source_assets")
    for index, raw_entry in enumerate(source_assets):
        entry = _mapping(raw_entry, f"manifest.source_assets[{index}]")
        _exact_keys(
            entry,
            {"path", "sha256", "role"},
            f"manifest.source_assets[{index}]",
        )
        _text(entry["role"], f"manifest.source_assets[{index}].role")
        _verify_asset(
            root,
            {"path": entry["path"], "sha256": entry["sha256"]},
            f"manifest.source_assets[{index}]",
        )
    boundaries = _mapping(manifest.get("boundaries"), "manifest.boundaries")
    if boundaries != {
        "real_requirement_material": "NOT_PROVIDED",
        "new_numeric_simulation_assumption": "NONE",
        "candidate_implementation": "PROHIBITED",
        "support_state_change": "PROHIBITED",
        "p5_02_auto_start": "PROHIBITED",
        "production_capacity_sla": "NOT_ESTABLISHED",
    }:
        raise QualificationError(
            "BOUNDARY_MISMATCH",
            "manifest.boundaries",
            "must preserve Simulation-only selection and no-auto-start boundaries",
        )
    return QualificationBundle(
        profile=profile,
        manifest=manifest,
        records=tuple(records),
        manifest_fingerprint=_file_fingerprint(manifest_file),
        verified_asset_count=1 + len(records) + len(source_assets),
    )


def _validate_support_boundaries(root: Path, records: Sequence[JsonObject]) -> JsonObject:
    capability_document = yaml.safe_load(
        (root / "schemas/rules/capability-registry.v1.yaml").read_text(encoding="utf-8")
    )
    capability_root = _mapping(capability_document, "capability_registry")
    capability_rows = {
        _text(row.get("capability"), "capability_registry.capabilities[].capability"): row
        for row in (
            _mapping(item, "capability_registry.capabilities[]")
            for item in _array(capability_root.get("capabilities"), "capability_registry.capabilities")
        )
    }
    rule_document = yaml.safe_load(
        (root / "schemas/rules/constraint-rule-sheet.v1.yaml").read_text(encoding="utf-8")
    )
    rule_root = _mapping(rule_document, "constraint_rule_sheet")
    deferred_rows = {
        _text(row.get("constraint_id"), "constraint_rule_sheet.deferred_rules[].constraint_id"): row
        for row in (
            _mapping(item, "constraint_rule_sheet.deferred_rules[]")
            for item in _array(rule_root.get("deferred_rules"), "constraint_rule_sheet.deferred_rules")
        )
    }
    observed: list[JsonObject] = []
    for record in records:
        candidate_id = cast(str, record["candidate_id"])
        if candidate_id not in CONSTRAINT_CANDIDATES:
            continue
        capability_key, constraint_id = CONSTRAINT_CANDIDATES[candidate_id]
        capability = capability_rows.get(capability_key)
        rule = deferred_rows.get(constraint_id)
        if capability is None or rule is None:
            raise QualificationError(
                "SUPPORT_BOUNDARY_MISSING",
                candidate_id,
                "capability or deferred rule is missing",
            )
        if (
            capability.get("status") != "UNSUPPORTED"
            or capability.get("precheck_behavior") != "UNSUPPORTED_CAPABILITY"
            or rule.get("status") != "UNSUPPORTED"
            or rule.get("capability") != capability_key
            or rule.get("behavior") is None
            or "reject" not in str(rule["behavior"])
        ):
            raise QualificationError(
                "SUPPORT_BOUNDARY_CHANGED",
                candidate_id,
                "candidate must remain explicit UNSUPPORTED_CAPABILITY",
            )
        observed.append(
            {
                "candidate_id": candidate_id,
                "capability_key": capability_key,
                "constraint_id": constraint_id,
                "status": "UNSUPPORTED",
                "precheck_behavior": "UNSUPPORTED_CAPABILITY",
            }
        )
    return {"constraint_candidate_count": len(observed), "candidates": observed}


def replay_benchmarks(root: Path, profile_names: Sequence[str]) -> list[JsonObject]:
    from app.simulation.benchmarks import (  # imported only for executable replay
        BenchmarkContractError,
        BenchmarkExecutionError,
        run_benchmark,
        validate_benchmark_report,
    )

    observations: list[JsonObject] = []
    for profile_name in profile_names:
        try:
            report = run_benchmark(
                root=root,
                profile_name=profile_name,
                require_baseline=True,
            )
            validate_benchmark_report(report)
        except (BenchmarkContractError, BenchmarkExecutionError) as error:
            raise QualificationError(
                "BENCHMARK_REPLAY_FAILED",
                f"benchmark.{profile_name}",
                str(error),
            ) from error
        if report.get("status") != "PASS" or report.get("warnings") != []:
            raise QualificationError(
                "BENCHMARK_REGRESSION",
                f"benchmark.{profile_name}",
                "approved profile must pass without warning before qualification",
            )
        global_solver = _mapping(report.get("global_solver"), f"benchmark.{profile_name}.global_solver")
        observations.append(
            {
                "profile": report["profile"],
                "problem": report["problem"],
                "status": report["status"],
                "check_count": report["check_count"],
                "runtime": global_solver["timings"],
                "memory": global_solver["memory_peak_mb"],
                "model_size": global_solver["model_metrics"],
                "quality": {
                    "solver": global_solver["quality"],
                    "comparison": report["comparison"],
                    "validation": global_solver["validation"],
                },
                "baseline": report["baseline"],
                "environment": report["environment"],
                "boundaries": report["boundaries"],
            }
        )
    return observations


def _check(name: str, evidence: object) -> JsonObject:
    return {"name": name, "status": "PASS", "evidence": evidence}


def _code_commit() -> str:
    value = os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted")
    if value == "uncommitted" or (
        len(value) == 40 and all(character in "0123456789abcdef" for character in value)
    ):
        return value
    return "uncommitted"


def build_report(root: Path, bundle: QualificationBundle) -> JsonObject:
    root = root.resolve()
    decisions = [decide_record(record, bundle.profile) for record in bundle.records]
    replayed = [decide_record(deepcopy(record), bundle.profile) for record in bundle.records]
    if [row["decision_fingerprint"] for row in decisions] != [
        row["decision_fingerprint"] for row in replayed
    ]:
        raise QualificationError(
            "NON_DETERMINISTIC_DECISION",
            "decisions",
            "same-input replay changed decision fingerprints",
        )

    positive = deepcopy(bundle.records[0])
    cast(JsonObject, cast(JsonObject, positive["evidence"])["benchmark"])[
        "qualified"
    ] = True
    positive["selection_facts"] = {name: True for name in REQUIRED_FACTS}
    positive["expected_decision"] = "SELECTED"
    positive_decision = decide_record(positive, bundle.profile)
    negative = deepcopy(positive)
    cast(JsonObject, negative["selection_facts"])[
        "candidate_specific_gate_passed"
    ] = False
    negative["expected_decision"] = "DEFERRED"
    negative_decision = decide_record(negative, bundle.profile)
    if positive_decision["decision"] != "SELECTED" or negative_decision["decision"] != "DEFERRED":
        raise QualificationError(
            "SELECTION_RULE_FAILURE",
            "selection_rule",
            "positive/negative rule replay did not fail closed",
        )

    benchmarks = replay_benchmarks(
        root,
        [cast(str, value) for value in cast(list[object], bundle.profile["benchmark_profiles"])],
    )
    support_boundaries = _validate_support_boundaries(root, bundle.records)
    selected = [cast(str, row["candidate_id"]) for row in decisions if row["decision"] == "SELECTED"]
    deferred = [cast(str, row["candidate_id"]) for row in decisions if row["decision"] == "DEFERRED"]
    if selected or tuple(deferred) != EXPECTED_CANDIDATES:
        raise QualificationError(
            "UNSUPPORTED_SELECTION",
            "portfolio",
            "current evidence qualifies no candidate; all nine must be DEFERRED",
        )
    decomposition = next(
        row for row in decisions if row["candidate_id"] == "P5-CANDIDATE-DECOMPOSITION"
    )
    rolling = next(
        row for row in decisions if row["candidate_id"] == "P5-CANDIDATE-ROLLING-HORIZON"
    )
    checks = [
        _check(
            "profile-contract-and-p5-boundary",
            {"profile_version": PROFILE_VERSION, "selection_operator": "ALL_TRUE"},
        ),
        _check(
            "raw-evidence-manifest-and-hashes",
            {
                "manifest_version": MANIFEST_VERSION,
                "manifest_fingerprint": bundle.manifest_fingerprint,
                "verified_asset_count": bundle.verified_asset_count,
            },
        ),
        _check(
            "nine-candidate-completeness",
            {"candidate_ids": list(EXPECTED_CANDIDATES), "decision_count": len(decisions)},
        ),
        _check(
            "real-simulation-benchmark-source-isolation",
            {"source_types": bundle.profile["source_types"], "real_material": "NOT_PROVIDED"},
        ),
        _check(
            "same-input-decision-replay",
            {"decision_fingerprints": [row["decision_fingerprint"] for row in decisions]},
        ),
        _check(
            "positive-negative-selection-rule",
            {"positive": positive_decision["decision"], "negative": negative_decision["decision"]},
        ),
        _check(
            "approved-xs-s-m-benchmark-replay",
            {
                "profiles": [row["profile"] for row in benchmarks],
                "statuses": [row["status"] for row in benchmarks],
                "warnings": 0,
            },
        ),
        _check(
            "decomposition-section-82-gate",
            {
                "decision": decomposition["decision"],
                "gate": decomposition["candidate_specific_gate"],
                "approved_profiles": ["XS", "S", "M"],
                "large_or_historical_trigger": False,
                "deployment_memory_budget": "NOT_DEFINED_OPEN_012",
                "advanced_constraint_explosion": False,
            },
        ),
        _check(
            "rolling-whole-horizon-comparison-gate",
            {
                "decision": rolling["decision"],
                "gate": rolling["candidate_specific_gate"],
                "window_step_overlap_handoff": "NOT_DEFINED",
                "rolling_vs_global_comparison": "NOT_AVAILABLE",
            },
        ),
        _check("unsupported-capability-status-preserved", support_boundaries),
        _check(
            "portfolio-no-big-bang-no-auto-start",
            {
                "selected": selected,
                "deferred": deferred,
                "p5_02_authorized": False,
                "capability_tasks_authorized": False,
            },
        ),
    ]
    semantic_projection = {
        "task_id": TASK_ID,
        "diff_base": DIFF_BASE,
        "manifest_fingerprint": bundle.manifest_fingerprint,
        "decisions": [
            {
                "candidate_id": row["candidate_id"],
                "decision": row["decision"],
                "decision_fingerprint": row["decision_fingerprint"],
            }
            for row in decisions
        ],
        "selected": selected,
        "deferred": deferred,
    }
    return {
        "report_version": REPORT_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "diff_base": DIFF_BASE,
        "code_commit": _code_commit(),
        "validation_profile": "HIGH_RISK",
        "impact_rules": list(IMPACT_RULES),
        "manifest": {
            "version": MANIFEST_VERSION,
            "fingerprint": bundle.manifest_fingerprint,
            "verified_asset_count": bundle.verified_asset_count,
        },
        "decisions": decisions,
        "portfolio": {
            "selected": selected,
            "deferred": deferred,
            "selected_count": len(selected),
            "deferred_count": len(deferred),
            "p5_02_authorized": False,
        },
        "benchmark_observations": benchmarks,
        "semantic_projection_fingerprint": canonical_fingerprint(semantic_projection),
        "check_count": len(checks),
        "checks": checks,
        "issues": [],
        "blocking_issues": [],
        "boundaries": {
            "candidate_support_states": "UNCHANGED_UNSUPPORTED",
            "planning_problem_solver_validator": "UNCHANGED",
            "schema_migration_dependency_state_workflow": "UNCHANGED",
            "p4_execution_replan_freeze_stability_change_report_simulator": "FROZEN_REGRESSION_CONTEXT",
            "new_sim_assumption": "NONE",
            "p5_02_and_capability_implementation": "NOT_AUTHORIZED_NOT_STARTED",
            "p6_plus": "EXCLUDED",
            "production_authority_external_deployment_capacity_sla": "NOT_ESTABLISHED",
        },
    }


def _failure_report(error: Exception) -> JsonObject:
    return {
        "report_version": REPORT_VERSION,
        "status": "FAIL",
        "task_id": TASK_ID,
        "diff_base": DIFF_BASE,
        "code_commit": _code_commit(),
        "validation_profile": "HIGH_RISK",
        "impact_rules": list(IMPACT_RULES),
        "check_count": 0,
        "checks": [],
        "issues": [
            {
                "code": getattr(error, "code", type(error).__name__),
                "field": getattr(error, "field", None),
                "message": getattr(error, "message", str(error)),
            }
        ],
        "blocking_issues": ["QUALIFICATION_EVIDENCE_INVALID"],
        "boundaries": {
            "partial_selection_claim": "PROHIBITED",
            "candidate_support_states": "UNCHANGED_UNSUPPORTED",
            "p5_02_auto_start": "PROHIBITED",
            "production_capacity_sla": "NOT_ESTABLISHED",
        },
    }


def _write_report(path: Path, report: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument(
        "--manifest",
        default="fixtures/simulation/p5/qualification/evidence-manifest.v1.json",
    )
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        bundle = load_qualification_bundle(root, manifest_path=args.manifest)
        report = build_report(root, bundle)
    except Exception as error:
        if not isinstance(error, (QualificationError, OSError)):
            raise
        report = _failure_report(error)
        _write_report(args.report, report)
        print(f"FAIL {TASK_ID}: {error}")
        return 1
    _write_report(args.report, report)
    print(
        f"PASS {TASK_ID}: decisions={len(report['decisions'])} "
        f"selected={report['portfolio']['selected_count']} "
        f"deferred={report['portfolio']['deferred_count']} "
        f"checks={report['check_count']} blocking=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DIFF_BASE",
    "EXPECTED_CANDIDATES",
    "IMPACT_RULES",
    "QualificationBundle",
    "QualificationError",
    "REPORT_VERSION",
    "TASK_ID",
    "build_report",
    "canonical_fingerprint",
    "decide_record",
    "load_qualification_bundle",
    "main",
    "replay_benchmarks",
    "validate_record",
]
