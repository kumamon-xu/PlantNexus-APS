"""The installed P9 process must consume the selected Kit identity."""

import os
from typing import Any

from app import RUNTIME_VERSION
from backend.tests.integration.test_p9_manual import runtime  # noqa: F401


def test_runtime_descriptor_binds_selected_kit_and_runtime(runtime: Any) -> None:  # noqa: F811
    descriptor = runtime.app.state.aps_runtime_descriptor
    resolution = descriptor.runtime_resolution
    assert resolution["runtime_version"] == RUNTIME_VERSION
    selected = os.environ.get("PLANTNEXUS_DEVELOPER_KIT_VERSION")
    if selected is not None:
        assert resolution["developer_kit_version"] == selected
        assert resolution["developer_kit_fingerprint"] == os.environ["PLANTNEXUS_DEVELOPER_KIT_FINGERPRINT"]
    assert runtime.source["state"] == "READY_FOR_REVIEW"
