"""Shared, solver-independent candidate admission; owns no business transaction."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import json
from typing import Protocol, cast

from app.data_validation.canonical_ingress import canonical_fingerprint
from app.extensions.contracts import RuntimeExtensionError
from app.planning.validation.problem_schedule_validator import ProblemScheduleValidator


class CandidateValidator(Protocol):
    def validate(
        self, problem: Mapping[str, object], candidate: Mapping[str, object]
    ) -> Mapping[str, object]: ...


type ExtensionValidation = Callable[[Mapping[str, object], Mapping[str, object]], None]
type IdentityProvider = Callable[[], Mapping[str, object]]


class CandidateAdmissionError(ValueError):
    """Sanitized execution/identity failure, distinct from a Core FAIL report."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Candidate admission rejected: {reason}")


def _bytes(value: Mapping[str, object]) -> bytes:
    return json.dumps(
        dict(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _copy(value: Mapping[str, object]) -> dict[str, object]:
    return cast(dict[str, object], json.loads(_bytes(value)))


@dataclass(frozen=True, slots=True)
class CandidateAdmission:
    """Immutable internal evidence; existing public report bytes remain unchanged."""

    problem_fingerprint: str
    candidate_fingerprint: str
    binding_fingerprint: str
    report_bytes: bytes
    extension_checked: bool

    @property
    def report(self) -> dict[str, object]:
        return cast(dict[str, object], json.loads(self.report_bytes))


class CandidateAdmissionService:
    """Fresh Core validation followed by the server-bound Extension validator.

    The default is the explicitly Core-only internal application composition.
    Extension compositions must supply both a validator and an identity provider
    containing Registry/configuration/Kit and scope identity. Owners retain their
    source-lineage, authorization, transaction and replay checks.
    """

    def __init__(
        self,
        *,
        validator_factory: Callable[[], CandidateValidator] | None = None,
        extension_validator: ExtensionValidation | None = None,
        identity_provider: IdentityProvider | None = None,
    ) -> None:
        if (extension_validator is None) != (identity_provider is None):
            raise CandidateAdmissionError("INCOMPLETE_EXTENSION_BINDING")
        self._validator_factory = (
            ProblemScheduleValidator if validator_factory is None else validator_factory
        )
        self._extension_validator = extension_validator
        self._identity_provider = identity_provider
        self._binding = self._current_binding()

    def _current_binding(self) -> bytes:
        try:
            return _bytes(
                self._identity_provider()
                if self._identity_provider is not None
                else {
                    "mode": "CORE_ONLY",
                    "validation_report_version": "validation-report.v2",
                }
            )
        except RuntimeExtensionError:
            raise
        except Exception as error:  # noqa: BLE001 - sanitize authority adapter
            raise CandidateAdmissionError("BINDING_UNAVAILABLE") from error

    def verify_current(self) -> None:
        """Recheck the bound authority immediately before the owner's write."""
        if self._current_binding() != self._binding:
            raise CandidateAdmissionError("STALE_BINDING")

    def verify(
        self,
        admission: CandidateAdmission,
        problem: Mapping[str, object],
        candidate: Mapping[str, object],
    ) -> None:
        """Bind the owner's pending write to the exact evaluated fact bytes."""
        self.verify_current()
        if (
            admission.problem_fingerprint != canonical_fingerprint(problem)
            or admission.candidate_fingerprint != canonical_fingerprint(candidate)
            or admission.binding_fingerprint
            != canonical_fingerprint(json.loads(self._binding))
        ):
            raise CandidateAdmissionError("STALE_INPUT_OR_BINDING")

    def evaluate(
        self, problem: Mapping[str, object], candidate: Mapping[str, object]
    ) -> CandidateAdmission:
        problem_bytes, candidate_bytes = _bytes(problem), _bytes(candidate)
        if self._current_binding() != self._binding:
            raise CandidateAdmissionError("STALE_BINDING")
        # Each evaluator gets a detached fact view, never Solver-owned references.
        core_problem, core_candidate = _copy(problem), _copy(candidate)
        try:
            validator = self._validator_factory()
            report = validator.validate(core_problem, core_candidate)
        except Exception as error:  # noqa: BLE001 - sanitize validator failures
            raise CandidateAdmissionError("VALIDATOR_EXECUTION_FAILED") from error
        if (
            _bytes(core_problem) != problem_bytes
            or _bytes(core_candidate) != candidate_bytes
        ):
            raise CandidateAdmissionError("VALIDATOR_MUTATED_INPUT")
        if not isinstance(report, Mapping):
            raise CandidateAdmissionError("INVALID_VALIDATION_REPORT")
        violations = report.get("violations")
        count = report.get("hard_violation_count")
        if (
            report.get("validation_report_version") != "validation-report.v2"
            or report.get("problem_hash") != problem.get("problem_hash")
            or not isinstance(violations, list)
            or type(count) is not int
            or count != len(violations)
            or report.get("status") != ("PASS" if count == 0 else "FAIL")
        ):
            raise CandidateAdmissionError("INVALID_VALIDATION_REPORT")
        report_bytes = _bytes(report)
        if count == 0 and type(validator) is not ProblemScheduleValidator:
            # An injected adapter cannot manufacture acceptance with a canned PASS.
            independent = ProblemScheduleValidator().validate(
                _copy(problem), _copy(candidate)
            )
            if _bytes(independent) != report_bytes:
                raise CandidateAdmissionError("VALIDATOR_BYPASS")
        checked = False
        if count == 0 and self._extension_validator is not None:
            extension_problem, extension_candidate = _copy(problem), _copy(candidate)
            try:
                self._extension_validator(extension_problem, extension_candidate)
            except RuntimeExtensionError:
                raise
            except Exception as error:  # noqa: BLE001 - sanitize injected adapter
                raise CandidateAdmissionError("EXTENSION_EXECUTION_FAILED") from error
            if (
                _bytes(extension_problem) != problem_bytes
                or _bytes(extension_candidate) != candidate_bytes
            ):
                raise CandidateAdmissionError("EXTENSION_MUTATED_INPUT")
            checked = True
        if (
            self._current_binding() != self._binding
            or _bytes(problem) != problem_bytes
            or _bytes(candidate) != candidate_bytes
        ):
            raise CandidateAdmissionError("STALE_INPUT_OR_BINDING")
        return CandidateAdmission(
            canonical_fingerprint(problem),
            canonical_fingerprint(candidate),
            canonical_fingerprint(json.loads(self._binding)),
            report_bytes,
            checked,
        )
