"""TEST-P9-ADMISSION-001: fresh authority, immutable views and fail-closed ports."""

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from app.application.candidate_admission import (
    CandidateAdmissionError,
    CandidateAdmissionService,
)
from app.application.schedule_version_lifecycle_check import load_fixed_validated_output
from app.planning.validation.problem_schedule_validator import ProblemScheduleValidator

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def output():
    return load_fixed_validated_output(ROOT)[0]


def test_admission_binds_actual_bytes_and_detaches_report(output):
    seen = []

    def extension(problem, candidate):
        assert problem is not output.problem and candidate is not output.solution
        seen.append((deepcopy(problem), deepcopy(candidate)))

    service = CandidateAdmissionService(
        extension_validator=extension,
        identity_provider=lambda: {"registry": "fixed"},
    )
    result = service.evaluate(output.problem, output.solution)
    assert result.extension_checked and result.report == output.validation_report
    result.report["status"] = "FAIL"
    assert result.report["status"] == "PASS"
    assert seen == [(output.problem, output.solution)]


@pytest.mark.parametrize(
    "failure",
    [
        "missing",
        "exception",
        "timeout",
        "malformed",
        "mutation",
        "stale-report",
        "bypass",
    ],
)
def test_validator_cannot_bypass_admission(output, failure):
    candidate = deepcopy(output.solution)
    if failure == "bypass":
        candidate["assignments"] = []

    class Validator:
        def validate(self, problem, value):
            if failure == "exception":
                raise RuntimeError("private-token")
            if failure == "timeout":
                raise TimeoutError("private-token")
            if failure == "malformed":
                return {"status": "PASS", "hard_violation_count": 0}
            if failure == "mutation":
                value["assignments"] = []
            report = deepcopy(output.validation_report)
            if failure == "stale-report":
                report["problem_hash"] = "sha256:" + "0" * 64
            return report

    factory: Any = (lambda: None) if failure == "missing" else Validator
    with pytest.raises(CandidateAdmissionError) as error:
        CandidateAdmissionService(validator_factory=factory).evaluate(
            output.problem, candidate
        )
    assert "private-token" not in str(error.value)
    assert output.solution["assignments"]


@pytest.mark.parametrize("when", ["before", "during", "before-write"])
def test_stale_registry_or_kit_is_rejected(output, when):
    identity = {"registry": "one", "kit": "fixed"}

    def extension(problem, candidate):
        if when == "during":
            identity["registry"] = "two"

    service = CandidateAdmissionService(
        extension_validator=extension, identity_provider=lambda: identity
    )
    if when == "before":
        identity["kit"] = "changed"
    if when == "before-write":
        service.evaluate(output.problem, output.solution)
        identity["kit"] = "changed"
        with pytest.raises(CandidateAdmissionError, match="STALE_BINDING"):
            service.verify_current()
    else:
        with pytest.raises(CandidateAdmissionError, match="STALE"):
            service.evaluate(output.problem, output.solution)


def test_missing_extension_validator_does_not_mean_empty_registry():
    with pytest.raises(CandidateAdmissionError, match="INCOMPLETE_EXTENSION_BINDING"):
        CandidateAdmissionService(identity_provider=lambda: {"registry": "required"})


def test_core_fail_does_not_invoke_extension(output):
    candidate = deepcopy(output.solution)
    candidate["assignments"] = []

    def extension(problem, value):
        pytest.fail("Core FAIL must not evaluate an Extension candidate")

    result = CandidateAdmissionService(
        extension_validator=extension, identity_provider=lambda: {}
    ).evaluate(output.problem, candidate)
    assert result.report == ProblemScheduleValidator().validate(
        output.problem, candidate
    )
    assert result.report["status"] == "FAIL" and not result.extension_checked


def test_extension_cannot_mutate_core_or_candidate(output):
    def extension(problem, candidate):
        candidate["assignments"].clear()

    with pytest.raises(CandidateAdmissionError, match="EXTENSION_MUTATED_INPUT"):
        CandidateAdmissionService(
            extension_validator=extension, identity_provider=lambda: {}
        ).evaluate(output.problem, output.solution)
    assert output.solution["assignments"]


def test_admission_has_no_solver_import():
    import ast

    source = (ROOT / "backend/app/application/candidate_admission.py").read_text(
        encoding="utf-8"
    )
    imports = [
        node.module or ""
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom)
    ]
    assert not any(
        "backends" in name or "strategies" in name or "ortools" in name
        for name in imports
    )


@pytest.mark.parametrize("target", ["problem", "candidate"])
def test_changed_facts_after_validation_cannot_be_written(output, target):
    problem, candidate = deepcopy(output.problem), deepcopy(output.solution)
    service = CandidateAdmissionService()
    receipt = service.evaluate(problem, candidate)
    if target == "problem":
        problem["problem_hash"] = "sha256:" + "0" * 64
    else:
        candidate["assignments"].clear()
    with pytest.raises(CandidateAdmissionError, match="STALE_INPUT_OR_BINDING"):
        service.verify(receipt, problem, candidate)


@pytest.mark.parametrize("error", [RuntimeError, TimeoutError])
def test_extension_adapter_failure_is_sanitized(output, error):
    def extension(problem, candidate):
        raise error("private-token")

    service = CandidateAdmissionService(
        extension_validator=extension, identity_provider=lambda: {}
    )
    with pytest.raises(
        CandidateAdmissionError, match="EXTENSION_EXECUTION_FAILED"
    ) as captured:
        service.evaluate(output.problem, output.solution)
    assert "private-token" not in str(captured.value)


def test_stale_problem_rejected_before_extension(output):
    problem = deepcopy(output.problem)
    problem["problem_hash"] = "sha256:" + "0" * 64

    def extension(problem, candidate):
        pytest.fail("invalid authority must not reach Extension")

    service = CandidateAdmissionService(
        extension_validator=extension, identity_provider=lambda: {}
    )
    with pytest.raises(CandidateAdmissionError, match="VALIDATOR_EXECUTION_FAILED"):
        service.evaluate(problem, output.solution)
