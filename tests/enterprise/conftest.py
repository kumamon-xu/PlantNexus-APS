import json
import pytest
from infra.enterprise.bootstrap import preflight
from tests.enterprise.configuration_fixtures import create_fixture


@pytest.fixture
def configured(tmp_path, monkeypatch):
    env = create_fixture(tmp_path)
    monkeypatch.setattr(preflight, "readonly", lambda _: True)
    root = tmp_path / "runtime"
    (root / "metadata").mkdir(parents=True)
    (root / "metadata/release-manifest.json").write_text(
        json.dumps(
            {
                "code_commit": preflight.SOURCE_SHA,
                "release_fingerprint": preflight.RUNTIME_FP,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(preflight, "RUNTIME_ROOT", root)
    return tmp_path, env
