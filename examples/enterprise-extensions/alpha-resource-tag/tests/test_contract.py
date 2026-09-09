from __future__ import annotations

import json
from pathlib import Path
import unittest

from aps_extension_sdk import (
    ConstraintContext,
    ExtensionInputView,
    ValidationContext,
    parse_extension_manifest,
)
from example_alpha_extension.constraint import AlphaResourceTagConstraint
from example_alpha_extension.validation import AlphaResourceTagValidator


ROOT = Path(__file__).resolve().parents[1]


class AlphaContractTests(unittest.TestCase):
    def setUp(self) -> None:
        document = json.loads(
            (ROOT / "extension/extension-manifest.json").read_text(encoding="utf-8")
        )
        self.manifest = parse_extension_manifest(document)

    def _view(self, contribution_id: str, tag: str | None) -> ExtensionInputView:
        return ExtensionInputView.from_json(
            view_contract_version="runtime.extension.input.v1",
            extension_id=self.manifest.extension_id,
            contribution_id=contribution_id,
            input_fingerprint="sha256:" + "a" * 64,
            scope={
                "extension_configuration": {
                    "values": {"required_tag": "alpha-qualified"}
                }
            },
            facts={
                "resources": [
                    {"resource_id": "resource-a", "tags": [tag] if tag else []}
                ],
                "assignments": [
                    {"operation_id": "operation-a", "resource_id": "resource-a"}
                ],
            },
            provenance={"fixture": "synthetic"},
        )

    def test_constraint_replays_identically(self) -> None:
        descriptor = self.manifest.contributions[0]
        target = AlphaResourceTagConstraint(descriptor)
        context = ConstraintContext(
            self._view(descriptor.contribution_id, "alpha-qualified")
        )
        self.assertEqual(target.contribute(context), target.contribute(context))

    def test_independent_validator_rejects_negative_fixture(self) -> None:
        descriptor = self.manifest.contributions[1]
        target = AlphaResourceTagValidator(descriptor)
        valid = target.validate(
            ValidationContext(self._view(descriptor.contribution_id, "alpha-qualified"))
        )
        invalid = target.validate(
            ValidationContext(self._view(descriptor.contribution_id, None))
        )
        self.assertTrue(valid.passed)
        self.assertFalse(invalid.passed)


if __name__ == "__main__":
    unittest.main()
