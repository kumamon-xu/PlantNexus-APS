"""Solver-neutral PlanningProblem construction and content identity boundary."""

from typing import TYPE_CHECKING, Any

from .contracts import (
    ImmutablePlanningProblem,
    PlanningProblemDocument,
    PlanningProblemError,
    PlanningProblemErrorCode,
)

if TYPE_CHECKING:
    from .builder import build_planning_problem
    from .hashing import (
        PLANNING_PROBLEM_VERSION,
        PROBLEM_BUILDER_VERSION,
        PROBLEM_CANONICALIZATION_VERSION,
        PROBLEM_HASH_PROJECTION_VERSION,
        canonical_problem_bytes,
        canonical_problem_document,
        problem_hash_for,
        problem_hash_projection,
        verify_problem,
    )

_HASHING_EXPORTS = {
    "PLANNING_PROBLEM_VERSION",
    "PROBLEM_BUILDER_VERSION",
    "PROBLEM_CANONICALIZATION_VERSION",
    "PROBLEM_HASH_PROJECTION_VERSION",
    "canonical_problem_bytes",
    "canonical_problem_document",
    "problem_hash_for",
    "problem_hash_projection",
    "verify_problem",
}


def __getattr__(name: str) -> Any:
    """Load implementation exports lazily so domain prechecks can import types."""

    if name == "build_planning_problem":
        from .builder import build_planning_problem

        return build_planning_problem
    if name in _HASHING_EXPORTS:
        from . import hashing

        return getattr(hashing, name)
    raise AttributeError(name)

__all__ = [
    "PLANNING_PROBLEM_VERSION",
    "PROBLEM_BUILDER_VERSION",
    "PROBLEM_CANONICALIZATION_VERSION",
    "PROBLEM_HASH_PROJECTION_VERSION",
    "ImmutablePlanningProblem",
    "PlanningProblemDocument",
    "PlanningProblemError",
    "PlanningProblemErrorCode",
    "build_planning_problem",
    "canonical_problem_bytes",
    "canonical_problem_document",
    "problem_hash_for",
    "problem_hash_projection",
    "verify_problem",
]
