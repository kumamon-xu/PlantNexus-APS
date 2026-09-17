"""Install the current wheel and replay manual HTTP contracts outside the checkout.

Dependencies come from the already lock-synchronized test environment. Application
and SDK imports must come from the fresh wheel, never its editable source tree.
Schemas/migrations and synthetic fixture helpers remain explicit test inputs.
"""

import hashlib
import json
from pathlib import Path
import site
import subprocess
import sys
import pytest


def test_manual_http_contracts_from_installed_wheel(
    tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    root = Path(__file__).resolve().parents[3]
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(tmp_path / "dist")],
        cwd=root,
        check=True,
        capture_output=True,
        timeout=180,
    )
    (wheel,) = (tmp_path / "dist").glob("*.whl")
    environment = tmp_path / "installed"
    subprocess.run(
        [sys.executable, "-m", "venv", "--without-pip", str(environment)],
        check=True,
        capture_output=True,
        timeout=60,
    )
    python = environment / (
        "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
    )
    subprocess.run(
        ["uv", "pip", "install", "--python", str(python), "--no-deps", str(wheel)],
        check=True,
        capture_output=True,
        timeout=60,
    )
    configuration = tmp_path / "pytest.ini"
    configuration.write_text("[pytest]\n", encoding="utf-8")
    evidence = tmp_path / "installed-junit.xml"
    installed_test = tmp_path / "test_p9_manual.py"
    installed_test.write_bytes(
        (root / "backend/tests/integration/test_p9_manual.py").read_bytes()
    )
    bootstrap = tmp_path / "verify.py"
    bootstrap.write_text(
        "import pathlib, sys\n"
        f"sys.path.extend({[str(root), *site.getsitepackages()]!r})\n"
        "import app, aps_extension_sdk\n"
        f"environment = pathlib.Path({str(environment)!r}).resolve()\n"
        "assert pathlib.Path(app.__file__).resolve().is_relative_to(environment)\n"
        "assert pathlib.Path(aps_extension_sdk.__file__).resolve().is_relative_to(environment)\n"
        "import pytest\n"
        f"raise SystemExit(pytest.main({['--noconftest', '-c', str(configuration), str(installed_test), '-q', '--junitxml', str(evidence)]!r}))\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [str(python), "-I", "-X", "utf8", str(bootstrap)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    request.node.user_properties.extend(
        [
            ("installed_wheel_sha256", hashlib.sha256(wheel.read_bytes()).hexdigest()),
            ("application_and_sdk_import", "verified installed wheel"),
        ]
    )
    report = root / "build/validation/P9-04"
    report.mkdir(parents=True, exist_ok=True)
    (report / "installed-wheel.xml").write_bytes(evidence.read_bytes())
    (report / "installed-wheel.json").write_text(
        json.dumps(
            {
                "result": "PASS",
                "wheel": wheel.name,
                "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
                "application_import": "installed wheel",
                "sdk_import": "installed wheel",
                "dependencies": "existing exact lock-synchronized environment",
                "test_inputs": "repository synthetic fixtures, schemas and migrations",
                "release_published": False,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
