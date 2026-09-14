from pathlib import Path
from copy import deepcopy
import json

import pytest

from scripts import enterprise_finalize as f
from tests.enterprise import test_bundle
from tests.enterprise.test_acceptance import evidence_pair

tree = test_bundle.tree
COMMIT = test_bundle.COMMIT


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(f.canonical(value))
    return path


@pytest.fixture
def inputs(tree, tmp_path, monkeypatch):
    directory, identity = tree
    identity["dirty"] = False
    stage = tmp_path / f.STAGING / "accepted"
    stage.mkdir(parents=True)
    archive = stage / (directory.name + ".tar.gz")
    bundle = f.seal(directory, identity, archive)
    bundle.update(code_commit=COMMIT)
    acceptance, _ = evidence_pair(COMMIT)
    acceptance["candidate"] = dict(bundle, packaging_commit=COMMIT)

    def provider(name, commit):
        folder = tmp_path / "build/provider" / name
        artifact = folder / "artifacts/evidence.zip"
        artifact.parent.mkdir(parents=True)
        artifact.write_bytes(b"synthetic provider bytes")
        return write(
            folder / "provider-evidence-manifest.json",
            {
                "result": "PASS",
                "implementation_sha": commit,
                "required_check": {"conclusion": "success"},
                "run": {"id": 123},
                "artifacts": [
                    {"archive_file": "evidence.zip", "sha256": f.sha(artifact)}
                ],
            },
        )

    # Reuse validation itself is covered by the existing canonical collector
    # suite. This fixture supplies an isolated, explicit Provider test double.
    monkeypatch.setattr(
        f, "load_reusable_manifest", lambda *a, **kw: {"result": "PASS"}
    )
    p28 = provider("P8-28", COMMIT)
    p29 = provider("P8-29", "9" * 40)
    reports = {}
    for name, value in (("bundle", bundle), ("acceptance", acceptance)):
        name = "ci-enterprise-image-" + name + ".json"
        reports[name] = f.sha(write(p28.parent / "extracted" / name, value))
    receipt = write(
        p28.parent / "bundle-delivery-receipt.json",
        {
            "status": "PASS",
            "implementation_sha": COMMIT,
            "provider_manifest_sha256": f.sha(p28),
            "reports": reports,
        },
    )
    completion = write(
        tmp_path / "build/validation/enterprise/P8-28/completion-manifest.json",
        {
            "task_id": "TASK-P8-28",
            "status": "PASS",
            "verdict": "READY",
            "production_ready": False,
            "issues": [],
            "implementation_sha": COMMIT,
            "provider_manifest": p28.relative_to(tmp_path).as_posix(),
            "provider_manifest_sha256": f.sha(p28),
            "bundle_receipt": receipt.relative_to(tmp_path).as_posix(),
            "bundle_receipt_sha256": f.sha(receipt),
            "candidate_archive": archive.relative_to(tmp_path).as_posix(),
            "candidate_archive_sha256": bundle["archive_sha256"],
            **{
                k: bundle[k]
                for k in (
                    "payload_fingerprint",
                    "images",
                    "checksums_sha256",
                    "manifest_sha256",
                )
            },
        },
    )
    return tmp_path, completion, p29, archive


def finish(inputs):
    root, completion, provider, _ = inputs
    report = f.finalize(root, completion, f.sha(completion), provider, "9" * 40)
    return write(root / f.EVIDENCE / "final-receipt.json", report)


def test_evidence_only_reseal_preserves_payload_and_original_archive(inputs):
    root, completion, _, source = inputs
    before = f.sha(source)
    receipt = finish(inputs)
    value = f.final_valid(root, receipt, f.sha(receipt))
    assert value["archive_sha256"] != before
    assert (
        value["payload_fingerprint"]
        == json.loads(completion.read_text())["payload_fingerprint"]
    )
    assert f.sha(source) == before
    assert value["packaging_commit"] == COMMIT
    assert value["implementation_sha"] == "9" * 40
    assert len(list((root / f.FINAL).iterdir())) == 2
    with pytest.raises(ValueError, match="FINAL_DIRECTORY_EXISTS"):
        finish(inputs)


@pytest.mark.parametrize(
    "mutation", ["completion", "payload", "source", "provider", "expired", "report"]
)
def test_finalize_rejects_untrusted_or_changed_inputs(inputs, monkeypatch, mutation):
    root, completion, provider, source = inputs
    expected = f.sha(completion)
    value = json.loads(completion.read_text())
    if mutation == "completion":
        expected = "0" * 64
    if mutation == "payload":
        value["payload_fingerprint"] = "0" * 64
        write(completion, value)
        expected = f.sha(completion)
    if mutation == "source":
        source.write_bytes(source.read_bytes() + b"tamper")
    if mutation == "provider":
        p = json.loads(provider.read_text())
        p["implementation_sha"] = "8" * 40
        write(provider, p)
    if mutation == "expired":
        monkeypatch.setattr(f, "load_reusable_manifest", lambda *a, **kw: None)
    if mutation == "report":
        (
            root / "build/provider/P8-28/extracted/ci-enterprise-image-acceptance.json"
        ).write_bytes(b"{}")
    with pytest.raises(ValueError):
        f.finalize(root, completion, expected, provider, "9" * 40)
    assert not (root / f.FINAL).exists()


def test_cleanup_dry_run_preserves_evidence_and_deletes_only_exact_staging(inputs):
    root, _, _, _ = inputs
    receipt = finish(inputs)
    old = root / f.STAGING / "failed/debug.json"
    write(old, {"status": "FAIL"})
    history = write(root / "build/provider/history.json", {"keep": True})
    backup = root / "build/runtime/database.dump"
    backup.parent.mkdir(parents=True)
    backup.write_bytes(b"keep rollback data")
    plan = f.plan_cleanup(root, receipt, f.sha(receipt))
    assert old.exists() and history.exists() and backup.exists()
    path = write(root / f.EVIDENCE / "cleanup-plan.json", plan)
    result = f.apply_cleanup(root, path, f.sha(path))
    assert result["staging_empty"]
    assert history.exists() and backup.read_bytes() == b"keep rollback data"
    assert (
        root / f.EVIDENCE / "retained-staging/failed/debug.json"
    ).read_bytes() == f.canonical({"status": "FAIL"})
    removed = result["removed_absolute_roots"]
    assert isinstance(removed, list)
    assert all(Path(p).is_relative_to(root / f.STAGING) for p in removed)
    f.final_valid(root, receipt, f.sha(receipt))


@pytest.mark.parametrize(
    "mutation", ["root", "preserve", "changed", "final", "plan-digest", "data"]
)
def test_cleanup_fails_closed_before_deleting(inputs, mutation):
    root, _, _, source = inputs
    receipt = finish(inputs)
    plan = deepcopy(f.plan_cleanup(root, receipt, f.sha(receipt)))
    if mutation == "root":
        plan["staging_root"] = str(root)
    if mutation == "preserve":
        plan["preserve_root"] = str(root)
    if mutation == "changed":
        source.write_bytes(source.read_bytes() + b"new")
    if mutation == "final":
        next((root / f.FINAL).glob("*.sha256")).write_bytes(b"bad")
    if mutation == "data":
        (root / f.STAGING / "database.dump").write_bytes(b"never delete")
    path = write(root / f.EVIDENCE / "cleanup-plan.json", plan)
    with pytest.raises(ValueError):
        f.apply_cleanup(
            root, path, "0" * 64 if mutation == "plan-digest" else f.sha(path)
        )
    assert source.exists()


def test_cleanup_rejects_parent_escape(tmp_path):
    with pytest.raises(ValueError, match="PATH_OUTSIDE_ROOT"):
        f.confined(tmp_path, tmp_path / "../elsewhere")
    with pytest.raises(ValueError, match="PATH_OUTSIDE_ROOT"):
        f.confined(tmp_path, tmp_path)


def test_only_named_scanner_cache_databases_are_disposable(tmp_path):
    cache = tmp_path / f.STAGING / "scan/trivy-cache/db/trivy.db"
    cache.parent.mkdir(parents=True)
    cache.write_bytes(b"synthetic disposable scanner cache")
    rows = f.inventory(tmp_path)
    assert next(r for r in rows if r["path"].endswith("trivy.db"))["preserve"] is False
    (cache.parent / "business.db").write_bytes(b"must not delete")
    with pytest.raises(ValueError, match="RECOVERY_DATA_REFUSED"):
        f.inventory(tmp_path)


def test_windows_reparse_point_is_rejected(tmp_path, monkeypatch):
    from types import SimpleNamespace

    target = tmp_path / "junction"
    target.mkdir()
    original = Path.lstat

    def lstat(path):
        if path == target:
            return SimpleNamespace(st_file_attributes=0x400, st_mode=0o40755)
        return original(path)

    monkeypatch.setattr(Path, "lstat", lstat)
    with pytest.raises(ValueError, match="LINK_OR_REPARSE_REFUSED"):
        f.confined(tmp_path, target)


def test_install_commands_have_explicit_seven_arguments():
    import shlex

    commands = [shlex.split(line) for line in f.install_commands().splitlines()]
    assert commands[0] == ["docker", "load", "--input", "$BUNDLE/images/runtime.tar"]
    for action, argv in zip(
        ("preflight", "install", "status"), commands[1:], strict=True
    ):
        assert argv == [
            "sh",
            f"$BUNDLE/scripts/{action}.sh",
            "$BUNDLE",
            "$CHECKSUMS",
            "$RUNTIME",
            "$SLOT",
            "$PROJECT",
            "$PORT",
            "$MODE",
        ]
