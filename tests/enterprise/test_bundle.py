from __future__ import annotations

from copy import deepcopy
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

import pytest

from infra.enterprise.bundle import builder
from infra.enterprise.bundle import verify as verifier

ROOT = Path(__file__).resolve().parents[2]
COMMIT = "1" * 40
NAME = "plantnexus-aps-enterprise-deployment-0.1.0-" + COMMIT


@pytest.fixture
def tree(tmp_path):
    directory = tmp_path / NAME
    directory.mkdir()
    images = {}
    lock = json.loads(
        (ROOT / "infra/enterprise/compose/dependencies.v1.json").read_text()
    )
    for i, n in enumerate(("runtime", "database", "redis"), 1):
        p = directory / "images" / (n + ".tar")
        p.parent.mkdir(exist_ok=True)
        p.write_bytes(("synthetic-image-" + n).encode())
        ref = lock["images"].get(n, "runtime:test")
        images[n] = dict(
            path="images/" + n + ".tar",
            tar_sha256=builder.sha(p),
            image_id="sha256:" + str(i) * 64,
            platform="linux/amd64",
            source_reference=ref,
            repo_digests_at_export=[]
            if n == "runtime"
            else [builder.digest_reference(ref)],
        )
        bom = directory / "SBOM" / (n + ".cdx.json")
        bom.parent.mkdir(exist_ok=True)
        bom.write_bytes(
            builder.canonical(dict(bomFormat="CycloneDX", components=[{"name": n}]))
        )
    for folder, dest in (
        ("scripts", "scripts"),
        ("bootstrap", "scripts/bootstrap"),
        ("compose", "compose"),
        ("config", "config"),
    ):
        for source in (ROOT / "infra/enterprise" / folder).iterdir():
            if source.is_file() and source.name != "verify_container.py":
                target = directory / dest / source.name
                builder.copy(source, target)
    enterprise = directory / "compose/docker-compose.enterprise.yml"
    enterprise.write_text(
        enterprise.read_text().replace(
            "source: ../bootstrap", "source: ../scripts/bootstrap"
        ),
        encoding="utf-8",
        newline="\n",
    )
    standalone = directory / "compose/docker-compose.standalone.yml"
    text = standalone.read_text()
    for n in ("database", "redis"):
        text = text.replace(lock["images"][n], images[n]["image_id"])
    standalone.write_text(text, encoding="utf-8", newline="\n")
    (directory / "images/identities.tsv").write_text(
        "".join(
            n + " " + images[n]["image_id"] + "\n"
            for n in ("runtime", "database", "redis")
        ),
        encoding="utf-8",
        newline="\n",
    )
    report = dict(
        status="PASS",
        issues=[],
        candidate=False,
        dirty=False,
        image_id=images["runtime"]["image_id"],
        image_archive_sha256=images["runtime"]["tar_sha256"],
        source_runtime_sha="2" * 40,
        code_commit="3" * 40,
    )
    (directory / "evidence").mkdir()
    (directory / "evidence/image-report.json").write_bytes(builder.canonical(report))
    (directory / "DEPLOYMENT.md").write_text(
        "synthetic test candidate\n", encoding="utf-8", newline="\n"
    )
    identity = dict(
        schema_version="enterprise-deployment-bundle.v1",
        status="CANDIDATE",
        production_ready=False,
        signature_present=False,
        independent_acceptance="P8-28_REQUIRED",
        packaging_commit=COMMIT,
        images=images,
        runtime_source_commit="2" * 40,
        image_packaging_commit="3" * 40,
        sdk_version="1.0.0",
        kit_version="1.0.0",
        kit_fingerprint="sha256:ee2a3a407337e595ca724ed2a92540e911c5fad7272e472f2d3ef3297a14a361",
        runtime_fingerprint="sha256:09559ca7f22af19c3f2b5fbb7f802c8d681574007fa31b2b8709ce5754b1083e",
        offline_modes=["enterprise", "standalone"],
    )
    return directory, identity


def raw_archive(path, members):
    with (
        path.open("wb") as raw,
        gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as compressed,
        tarfile.open(fileobj=compressed, mode="w|", format=tarfile.USTAR_FORMAT) as out,
    ):
        for info, data in members:
            out.addfile(info, io.BytesIO(data) if info.isfile() else None)


def get_members(archive):
    with tarfile.open(archive, "r:gz") as source:
        result = []
        for info in source:
            data = source.extractfile(info)
            assert data is not None
            result.append((info, data.read()))
        return result


def test_roundtrip_reproducible_inventory_and_executable_modes(tree, tmp_path):
    directory, identity = tree
    a, b = tmp_path / "a.tar.gz", tmp_path / "b.tar.gz"
    report = builder.seal(directory, identity, a)
    assert (
        builder.seal(directory, identity, b)["archive_sha256"]
        == report["archive_sha256"]
    )
    assert (
        Path(str(a) + ".sha256").read_text()
        == report["archive_sha256"] + "  a.tar.gz\n"
    )
    checked = verifier.extract(a, report["archive_sha256"], tmp_path / "unpacked")
    assert checked["payload_fingerprint"] == report["payload_fingerprint"]
    for info, _ in get_members(a):
        assert info.mode == (0o755 if info.name.endswith(".sh") else 0o644)


@pytest.mark.parametrize(
    "name",
    [
        "/absolute",
        "../escape",
        "root/../escape",
        "root//alias",
        "root/./alias",
        "C:/escape",
        "root\\escape",
        "root/a b",
        "root/a\nother",
    ],
)
def test_unsafe_archive_path_rejected_before_extract(tmp_path, name):
    info = tarfile.TarInfo(name)
    info.size, info.mode = 1, 0o644
    archive = tmp_path / "bad.tar.gz"
    raw_archive(archive, [(info, b"x")])
    with pytest.raises(ValueError, match="UNSAFE_PATH"):
        verifier.extract(archive, verifier.sha(archive), tmp_path / "target")
    assert not (tmp_path / "target").exists()


@pytest.mark.parametrize(
    "kind",
    [
        tarfile.SYMTYPE,
        tarfile.LNKTYPE,
        tarfile.CHRTYPE,
        tarfile.FIFOTYPE,
        tarfile.DIRTYPE,
    ],
)
def test_nonregular_members_rejected(tmp_path, kind):
    info = tarfile.TarInfo(NAME + "/evil")
    info.type, info.linkname = kind, "../../escape"
    path = tmp_path / "bad.tar.gz"
    raw_archive(path, [(info, b"")])
    with pytest.raises(ValueError, match="REGULAR_MEMBER_REQUIRED"):
        verifier.verify(path, verifier.sha(path))


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("duplicate", "DUPLICATE_MEMBER"),
        ("missing", "INVENTORY_MISMATCH"),
        ("tamper", "INVENTORY_MISMATCH"),
        ("mode", "MEMBER_METADATA_INVALID"),
        ("root", "SINGLE_ROOT_REQUIRED"),
    ],
)
def test_structural_corruption_rejected_with_fresh_outer_digest(
    tree, tmp_path, mutation, code
):
    directory, identity = tree
    archive = tmp_path / "good.tar.gz"
    builder.seal(directory, identity, archive)
    members = get_members(archive)
    i = next(
        i for i, (m, _) in enumerate(members) if m.name.endswith("scripts/start.sh")
    )
    if mutation == "duplicate":
        members.append(members[i])
    elif mutation == "missing":
        members.pop(i)
    elif mutation == "tamper":
        m, data = members[i]
        members[i] = m, b"x" * len(data)
    elif mutation == "mode":
        members[i][0].mode = 0o644
    elif mutation == "root":
        members[i][0].name = "different/scripts/start.sh"
    bad = tmp_path / "bad.tar.gz"
    raw_archive(bad, members)
    with pytest.raises(ValueError, match=code):
        verifier.verify(bad, verifier.sha(bad))


@pytest.mark.parametrize(
    "change,code",
    [
        ("image", "IMAGE_TAR_MISMATCH"),
        ("closure", "IMAGE_CLOSURE_MISSING"),
        ("platform", "IMAGE_IDENTITY_INVALID"),
        ("digest", "DEPENDENCY_DIGEST_MISSING"),
        ("source", "SOURCE_BINDING_INVALID"),
        ("production", "SCOPE_INVALID"),
        ("acceptance", "ACCEPTANCE_NOT_PERFORMED"),
    ],
)
def test_resealed_semantic_identity_attacks_refused(tree, tmp_path, change, code):
    directory, original = tree
    identity = deepcopy(original)
    if change == "image":
        identity["images"]["database"]["tar_sha256"] = "0" * 64
    elif change == "closure":
        del identity["images"]["redis"]
    elif change == "platform":
        identity["images"]["redis"]["platform"] = "linux/arm64"
    elif change == "digest":
        identity["images"]["database"]["repo_digests_at_export"] = []
    elif change == "source":
        identity["runtime_source_commit"] = "4" * 40
    elif change == "production":
        identity["production_ready"] = True
    elif change == "acceptance":
        identity["independent_acceptance"] = "READY"
    with pytest.raises(ValueError, match=code):
        builder.seal(directory, identity, tmp_path / "invalid.tar.gz")


@pytest.mark.parametrize(
    "data,code",
    [
        (b"-----BEGIN PRIVATE KEY-----\n", "SECRET_DETECTED"),
        (b"line\r\n", "LF_REQUIRED"),
        (b"postgresql://username:password@host\n", "SECRET_DETECTED"),
    ],
)
def test_text_secret_and_line_ending_gate(tree, tmp_path, data, code):
    directory, identity = tree
    (directory / "DEPLOYMENT.md").write_bytes(data)
    with pytest.raises(ValueError, match=code):
        builder.seal(directory, identity, tmp_path / "bad.tar.gz")


def test_late_evidence_changes_archive_not_payload_identity(tree, tmp_path):
    directory, identity = tree
    first = builder.seal(directory, identity, tmp_path / "first.tar.gz")
    (directory / "evidence/late.json").write_bytes(b'{"scope":"synthetic"}\n')
    second = builder.seal(directory, identity, tmp_path / "second.tar.gz")
    assert first["archive_sha256"] != second["archive_sha256"]
    assert first["payload_fingerprint"] == second["payload_fingerprint"]
    (directory / "scripts/start.sh").write_bytes(
        (directory / "scripts/start.sh").read_bytes() + b"# changed executable\n"
    )
    third = builder.seal(directory, identity, tmp_path / "third.tar.gz")
    assert second["payload_fingerprint"] != third["payload_fingerprint"]


def test_checksum_and_existing_destination_refused(tree, tmp_path):
    directory, identity = tree
    archive = tmp_path / "good.tar.gz"
    result = builder.seal(directory, identity, archive)
    with pytest.raises(ValueError, match="ARCHIVE_CHECKSUM_MISMATCH"):
        verifier.verify(archive, "0" * 64)
    with pytest.raises(ValueError, match="NEW_EXTRACTION_DIRECTORY_REQUIRED"):
        verifier.extract(archive, result["archive_sha256"], directory)
    with pytest.raises(ValueError, match="OUTPUT_EXISTS"):
        builder.seal(directory, identity, archive)


def test_duplicate_json_key_is_not_last_value_wins():
    with pytest.raises(ValueError, match="DUPLICATE_JSON_KEY"):
        verifier.parse(b'{"status":"FAIL","status":"PASS"}')


@pytest.mark.parametrize("constant", [b"NaN", b"Infinity", b"-Infinity"])
def test_nonfinite_json_refused(constant):
    with pytest.raises(ValueError, match="NONFINITE_JSON"):
        verifier.parse(b'{"value":' + constant + b"}")


def test_same_version_wrong_kit_bytes_refused(tree, tmp_path):
    directory, identity = tree
    identity["kit_fingerprint"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="COMPATIBILITY_IDENTITY_INVALID"):
        builder.seal(directory, identity, tmp_path / "wrong-kit.tar.gz")


def test_exported_image_config_digest_and_platform(tmp_path):
    config = builder.canonical(dict(os="linux", architecture="amd64"))
    image_id = "sha256:" + hashlib.sha256(config).hexdigest()
    archive = tmp_path / "image.tar"
    with tarfile.open(archive, "w") as out:
        for name, data in (
            ("config.json", config),
            (
                "manifest.json",
                builder.canonical([{"Config": "config.json", "Layers": []}]),
            ),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            out.addfile(info, io.BytesIO(data))
    builder.image_config(archive, image_id)
    with pytest.raises(ValueError, match="IMAGE_CONFIG_ID_MISMATCH"):
        builder.image_config(archive, "sha256:" + "0" * 64)


def test_expansion_and_member_limits_are_fail_closed(tree, tmp_path, monkeypatch):
    directory, identity = tree
    archive = tmp_path / "good.tar.gz"
    report = builder.seal(directory, identity, archive)
    monkeypatch.setattr(verifier, "MAX_BYTES", 1)
    with pytest.raises(ValueError, match="EXPANSION_LIMIT"):
        verifier.verify(archive, report["archive_sha256"])
    monkeypatch.setattr(verifier, "MAX_BYTES", 6 * 1024**3)
    monkeypatch.setattr(verifier, "MAX_MEMBERS", 1)
    with pytest.raises(ValueError, match="MEMBER_LIMIT"):
        verifier.verify(archive, report["archive_sha256"])
