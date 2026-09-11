"""Inspect the installed wheel without a checkout, development tools or network."""

from __future__ import annotations

import importlib.metadata
import json
import os
from pathlib import Path
import shutil


def main() -> None:
    import app
    import app.api.app
    import app.jobs.planning_run_solver_worker
    from app.planning.validation.problem_schedule_validator import validate_problem_schedule
    from aps_extension_sdk.manifest import SDK_API_VERSION

    assert app.api.app.app is not None
    assert app.jobs.planning_run_solver_worker.__name__.endswith("planning_run_solver_worker")
    uid = getattr(os, "getuid")()
    assert uid == 10001
    assert callable(validate_problem_schedule)
    assert SDK_API_VERSION == "1.0.0"
    assert not any(shutil.which(name) for name in ("uv", "npm", "git", "gcc", "pip", "pip3"))
    assert not Path("/workspace").exists()
    assert not Path("/opt/plantnexus/backend/app").exists()
    packages = sorted(
        [{"name": d.metadata["Name"], "version": d.version,
          "license": d.metadata.get("License-Expression") or d.metadata.get("License")}
         for d in importlib.metadata.distributions()], key=lambda d: d["name"] or ""
    )
    print(json.dumps({"status": "PASS", "uid": uid, "sdk_version": SDK_API_VERSION,
                      "application_version": importlib.metadata.version("plantnexus-aps"),
                      "roles": ["api", "worker", "migration", "validator"], "packages": packages}))


if __name__ == "__main__":
    main()
