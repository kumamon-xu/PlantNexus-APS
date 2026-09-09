"""SDK-only smoke tests copied into the generated enterprise project."""

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
from __PACKAGE_NAME__.constraint import ResourceTagConstraint
from __PACKAGE_NAME__.validation import ResourceTagValidationRule


ROOT = Path(__file__).resolve().parents[1]


class ExtensionContractTests(unittest.TestCase):
    def setUp(self) -> None:
        document = json.loads(
            (ROOT / "extension/extension-manifest.json").read_text(encoding="utf-8")
        )
        self.manifest = parse_extension_manifest(document)

    def _view(self, contribution_id: str, *, qualified: bool) -> ExtensionInputView:
        return ExtensionInputView.from_json(
            view_contract_version="runtime.extension.input.v1",
            extension_id=self.manifest.extension_id,
            contribution_id=contribution_id,
            input_fingerprint="sha256:" + "a" * 64,
            scope={
                "extension_configuration": {"values": {"required_tag": "qualified"}}
            },
            facts={
                "resources": [
                    {
                        "resource_id": "resource-001",
                        "tags": ["qualified"] if qualified else [],
                    }
                ],
                "assignments": [
                    {"operation_id": "operation-001", "resource_id": "resource-001"}
                ],
            },
            provenance={"fixture": "synthetic"},
        )

    def test_constraint_is_deterministic(self) -> None:
        descriptor = self.manifest.contributions[0]
        implementation = ResourceTagConstraint(descriptor)
        context = ConstraintContext(
            self._view(descriptor.contribution_id, qualified=True)
        )
        self.assertEqual(
            implementation.contribute(context), implementation.contribute(context)
        )

    def test_validator_independently_rejects_missing_tag(self) -> None:
        descriptor = self.manifest.contributions[1]
        implementation = ResourceTagValidationRule(descriptor)
        valid = implementation.validate(
            ValidationContext(self._view(descriptor.contribution_id, qualified=True))
        )
        invalid = implementation.validate(
            ValidationContext(self._view(descriptor.contribution_id, qualified=False))
        )
        self.assertTrue(valid.passed)
        self.assertFalse(invalid.passed)


if __name__ == "__main__":
    unittest.main()
