"""Order-independent seed plumbing and canonical JSON primitives for P0."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from app.simulation.scenarios.contracts import (
    MAX_SEED,
    require_identity,
    require_seed,
    require_semver,
)


CANONICALIZATION_VERSION = "canonical-json.v1"


class DeterminismContractError(ValueError):
    """A value cannot be represented by the P0 canonicalization contract."""


def canonical_json_bytes(value: object) -> bytes:
    """Serialize JSON with stable keys, separators, Unicode, and no NaN/Infinity."""

    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as error:
        raise DeterminismContractError(
            "value is not finite JSON-compatible data"
        ) from error
    return text.encode("utf-8")


def dataset_sha256(canonical_dataset: bytes) -> str:
    """Return the lowercase algorithm-qualified dataset digest."""

    return f"sha256:{hashlib.sha256(canonical_dataset).hexdigest()}"


@dataclass(frozen=True, slots=True)
class SeedMaterial:
    """Derive independent layer values without mutable or global RNG state."""

    root_seed: int
    generator_id: str
    generator_version: str
    namespace: str = "root"

    def __post_init__(self) -> None:
        require_seed(self.root_seed)
        require_identity(self.generator_id, "generator_id")
        require_semver(self.generator_version, "generator_version")
        require_identity(self.namespace, "seed namespace")

    def child(self, namespace: str) -> SeedMaterial:
        """Create a named child stream; creation/call order cannot affect values."""

        child_name = require_identity(namespace, "seed child namespace")
        return SeedMaterial(
            root_seed=self.root_seed,
            generator_id=self.generator_id,
            generator_version=self.generator_version,
            namespace=f"{self.namespace}/{child_name}",
        )

    def derive_uint64(self, label: str, *, index: int = 0) -> int:
        """Derive a stable unsigned 64-bit value for a named position."""

        label_value = require_identity(label, "seed label")
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            raise DeterminismContractError("seed index must be a non-negative integer")
        payload = canonical_json_bytes(
            {
                "generator_id": self.generator_id,
                "generator_version": self.generator_version,
                "index": index,
                "label": label_value,
                "namespace": self.namespace,
                "root_seed": self.root_seed,
            }
        )
        return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")

    def derive_seed(self, label: str, *, index: int = 0) -> int:
        """Return a derived value valid for the ScenarioSpec seed range."""

        return self.derive_uint64(label, index=index) & MAX_SEED

    def deterministic_index(
        self, size: int, label: str, *, index: int = 0
    ) -> int:
        """Select an index deterministically; this is not a distribution claim."""

        if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
            raise DeterminismContractError("selection size must be a positive integer")
        return self.derive_uint64(label, index=index) % size


__all__ = [
    "CANONICALIZATION_VERSION",
    "DeterminismContractError",
    "SeedMaterial",
    "canonical_json_bytes",
    "dataset_sha256",
]
