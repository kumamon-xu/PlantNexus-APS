from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from infra.enterprise.bootstrap import preflight, run
from tests.enterprise.configuration_fixtures import CANARY, write_env


def test_secret_bytes_and_dsn_never_enter_summary_or_errors(configured, capsys):
    directory, env = configured
    value = preflight.prepare(write_env(directory, env))
    assert CANARY not in repr(value) + json.dumps(value.report())
    Path(env["DB_PASSWORD_FILE"]).write_text(CANARY + "\nextra", encoding="utf-8")
    assert run.main(["--config", str(directory / "deployment.env"), "--check"]) == 1
    output = capsys.readouterr()
    assert CANARY not in output.out + output.err


def test_fragmented_secret_redaction_and_bounded_output():
    output = io.StringIO()
    stream = run.RedactedStream(output, (CANARY,))
    stream.write(CANARY[:14])
    stream.flush()
    assert output.getvalue() == ""
    stream.write(CANARY[14:] + "\n")
    stream.write("x" * 9000 + CANARY + "\n")
    assert CANARY not in output.getvalue()
    assert "[REDACTED]" in output.getvalue() and "OVERSIZE" in output.getvalue()


def test_multiline_keys_and_invalid_cli_are_sanitized(capsys):
    output = io.StringIO()
    stream = run.RedactedStream(output, ("first-private-line\nsecond-private-line",))
    stream.write("first-private-line\nsecond-private-line\n")
    assert "private-line" not in output.getvalue()
    assert run.main(["--role", CANARY]) == 1
    assert CANARY not in capsys.readouterr().out


@pytest.mark.parametrize(
    "mode", ["missing", "empty", "placeholder", "writable", "directory"]
)
def test_invalid_secret_files_rejected(configured, monkeypatch, mode):
    directory, env = configured
    path = Path(env["DB_PASSWORD_FILE"])
    if mode == "missing":
        path.unlink()
    elif mode == "empty":
        path.write_bytes(b"")
    elif mode == "placeholder":
        path.write_bytes(b"__REQUIRED__")
    elif mode == "directory":
        path.unlink()
        path.mkdir()
    else:
        monkeypatch.setattr(preflight, "readonly", lambda p: p != path)
    with pytest.raises(preflight.BootstrapError):
        preflight.prepare(write_env(directory, env))
