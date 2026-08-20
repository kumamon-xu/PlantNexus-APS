"""Solver-neutral PlanningProblem construction and content identity boundary."""

from typing import TYPE_CHECKING, Any

from .contracts import (
    DemandPriorityInput,
    ImmutablePlanningProblem,
    ImmutablePlanningProblemV2,
    PlanningProblemDocument,
    PlanningProblemDocumentV2,
    PlanningProblemError,
    PlanningProblemErrorCode,
)

if TYPE_CHECKING:
    from .builder import build_planning_problem, build_planning_problem_v2
    from .hashing import (
        PLANNING_PROBLEM_VERSION,
        PLANNING_PROBLEM_VERSION_V2,
        PROBLEM_BUILDER_VERSION,
        PROBLEM_BUILDER_VERSION_V2,
        PROBLEM_CANONICALIZATION_VERSION,
        PROBLEM_HASH_PROJECTION_VERSION,
        PROBLEM_HASH_PROJECTION_VERSION_V2,
        PROBLEM_SCHEMA_SET_VERSION_V2,
        canonical_problem_bytes,
        canonical_problem_document,
        canonical_problem_document_v2,
        canonical_problem_v2_bytes,
        problem_hash_for,
        problem_hash_projection,
        problem_v2_hash_for,
        problem_v2_hash_projection,
        verify_problem,
        verify_problem_v2,
    )

_HASHING_EXPORTS = {
    "PLANNING_PROBLEM_VERSION",
    "PLANNING_PROBLEM_VERSION_V2",
    "PROBLEM_BUILDER_VERSION",
    "PROBLEM_BUILDER_VERSION_V2",
    "PROBLEM_CANONICALIZATION_VERSION",
    "PROBLEM_HASH_PROJECTION_VERSION",
    "PROBLEM_HASH_PROJECTION_VERSION_V2",
    "PROBLEM_SCHEMA_SET_VERSION_V2",
    "canonical_problem_bytes",
    "canonical_problem_document",
    "canonical_problem_document_v2",
    "canonical_problem_v2_bytes",
    "problem_hash_for",
    "problem_hash_projection",
    "problem_v2_hash_for",
    "problem_v2_hash_projection",
    "verify_problem",
    "verify_problem_v2",
}


def __getattr__(name: str) -> Any:
    """Load implementation exports lazily so domain prechecks can import types."""

    if name in {"build_planning_problem", "build_planning_problem_v2"}:
        from . import builder

        return getattr(builder, name)
    if name in _HASHING_EXPORTS:
        from . import hashing

        return getattr(hashing, name)
    raise AttributeError(name)

__all__ = [
    "PLANNING_PROBLEM_VERSION",
    "PROBLEM_BUILDER_VERSION",
    "PROBLEM_CANONICALIZATION_VERSION",
    "PROBLEM_HASH_PROJECTION_VERSION",
    "PLANNING_PROBLEM_VERSION_V2",
    "PROBLEM_BUILDER_VERSION_V2",
    "PROBLEM_HASH_PROJECTION_VERSION_V2",
    "PROBLEM_SCHEMA_SET_VERSION_V2",
    "DemandPriorityInput",
    "ImmutablePlanningProblem",
    "ImmutablePlanningProblemV2",
    "PlanningProblemDocument",
    "PlanningProblemDocumentV2",
    "PlanningProblemError",
    "PlanningProblemErrorCode",
    "build_planning_problem",
    "build_planning_problem_v2",
    "canonical_problem_bytes",
    "canonical_problem_document",
    "canonical_problem_document_v2",
    "canonical_problem_v2_bytes",
    "problem_hash_for",
    "problem_hash_projection",
    "problem_v2_hash_for",
    "problem_v2_hash_projection",
    "verify_problem",
    "verify_problem_v2",
]
