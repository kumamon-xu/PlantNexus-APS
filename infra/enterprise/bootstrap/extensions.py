"""Read one operator-approved local wheel set; no signing, install or discovery."""

from __future__ import annotations

import hmac
import importlib
import io
from pathlib import Path, PurePosixPath
from queue import Queue
import re
import sys
from threading import Thread
from typing import Any
import zipfile

from .preflight import (
    BootstrapError,
    KIT_FP,
    SOURCE_SHA,
    fail,
    fingerprint,
    read_file,
    strict_json,
)


STARTUP_TIMEOUT_SECONDS = 30


def load_local_extensions(env: dict[str, str], key: str) -> tuple[Any, ...]:
    result: Queue[tuple[bool, Any]] = Queue(maxsize=1)

    def invoke():
        try:
            result.put((True, _load(env, key)))
        except Exception as error:
            result.put((False, error))

    thread = Thread(target=invoke, daemon=True, name="enterprise-local-extension")
    thread.start()
    thread.join(STARTUP_TIMEOUT_SECONDS)
    if thread.is_alive():
        raise BootstrapError("EXTENSION_STARTUP_TIMEOUT", "extension")
    succeeded, value = result.get_nowait()
    if succeeded:
        return value
    if isinstance(value, BootstrapError):
        raise value from None
    raise BootstrapError("EXTENSION_INVALID", "extension") from None


def _load(env: dict[str, str], key: str) -> tuple[Any, ...]:
    from aps_extension_sdk import canonical_json_bytes, parse_extension_manifest
    from app.extensions.contracts import RuntimeExtensionArtifact
    from app.extensions.loader import (
        load_runtime_extensions,
        runtime_extension_signature,
    )

    lock = strict_json(
        read_file(env["EXTENSION_LOCK_FILE"], "EXTENSION_LOCK_FILE"), "extension"
    )
    if (
        set(lock)
        != {
            "lock_version",
            "runtime_source_sha",
            "kit_version",
            "kit_fingerprint",
            "catalog_fingerprint",
            "artifacts",
        }
        or lock["lock_version"] != "enterprise-extension-lock.v1"
        or lock["runtime_source_sha"] != SOURCE_SHA
        or lock["kit_version"] != "1.0.0"
        or lock["kit_fingerprint"] != KIT_FP
    ):
        fail("extension", "EXTENSION_IDENTITY_MISMATCH")
    path = Path(env["EXTENSION_CATALOG_FILE"])
    catalog = strict_json(read_file(path, "EXTENSION_CATALOG_FILE"), "extension")
    basis = {k: v for k, v in catalog.items() if k != "catalog_fingerprint"}
    if (
        fingerprint(canonical_json_bytes(basis)) != catalog["catalog_fingerprint"]
        or lock["catalog_fingerprint"] != catalog["catalog_fingerprint"]
    ):
        fail("extension", "EXTENSION_IDENTITY_MISMATCH")
    entries = catalog["extensions"]
    locked = lock["artifacts"]
    if (
        not isinstance(entries, list)
        or not 1 <= len(entries) <= 32
        or not isinstance(locked, list)
    ):
        fail("extension")
    ids = [e["extension_id"] for e in entries]
    if ids != sorted(set(ids)) or [a["extension_id"] for a in locked] != ids:
        fail("extension", "EXTENSION_SET_MISMATCH")
    prepared = []
    for entry, artifact in zip(entries, locked, strict=True):
        if set(artifact) != {
            "extension_id",
            "extension_version",
            "wheel_file",
            "artifact_digest",
        }:
            fail("extension")
        if any(
            artifact[n] != entry[n]
            for n in ("extension_id", "extension_version", "artifact_digest")
        ):
            fail("extension", "EXTENSION_IDENTITY_MISMATCH")
        if entry["signature_key_id"] != env[
            "EXTENSION_KEY_ID"
        ] or not hmac.compare_digest(
            entry["signature"],
            runtime_extension_signature(entry, verification_key=key.encode()),
        ):
            fail("extension", "EXTENSION_SIGNATURE_INVALID")
        documents = {}
        for name in ("manifest_path", "configuration_path"):
            relative = PurePosixPath(entry[name])
            if relative.is_absolute() or ".." in relative.parts or "\\" in entry[name]:
                fail("extension", "UNSAFE_FILE")
            documents[name] = strict_json(
                read_file(path.parent / relative, "extension"), "extension"
            )
        manifest = parse_extension_manifest(documents["manifest_path"])
        raw = read_file(artifact["wheel_file"], "extension", limit=32 * 1024**2)
        if (
            fingerprint(raw) != artifact["artifact_digest"]
            or manifest.extension_id != entry["extension_id"]
        ):
            fail("extension", "EXTENSION_IDENTITY_MISMATCH")
        wheel = Path(artifact["wheel_file"])
        if wheel.suffix != ".whl":
            fail("extension")
        modules = {c.implementation.split(":")[0] for c in manifest.contributions}
        packages = {m.split(".")[0] for m in modules}
        if packages & {"app", "aps_extension_sdk", "bootstrap"} or any(
            not re.fullmatch(r"[A-Za-z_]\w*(\.[A-Za-z_]\w*)*", m) for m in modules
        ):
            fail("extension", "EXTENSION_IMPORT_INVALID")
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            if len(z.namelist()) != len(set(z.namelist())):
                fail("extension")
            total = 0
            for member in z.infolist():
                p = PurePosixPath(member.filename)
                total += member.file_size
                if (
                    p.is_absolute()
                    or ".." in p.parts
                    or "\\" in member.filename
                    or total > 64 * 1024**2
                    or (member.external_attr >> 16) & 0o170000 == 0o120000
                ):
                    fail("extension", "UNSAFE_FILE")
                if p.suffix == ".py" and p.parts[0] not in packages:
                    fail("extension", "EXTENSION_IMPORT_INVALID")
        for module in list(sys.modules):
            if module.split(".")[0] in packages:
                origin = str(getattr(sys.modules[module], "__file__", ""))
                if not origin.startswith(str(wheel) + "/") and not origin.startswith(
                    str(wheel) + "\\"
                ):
                    fail("extension", "EXTENSION_IMPORT_CONFLICT")
        prepared.append((wheel, raw, manifest))
    # All wheel digests/signatures are verified before the first trusted import.
    artifacts = []
    for wheel, raw, manifest in prepared:
        implementations = {}
        sys.path.insert(0, str(wheel))
        try:
            for descriptor in manifest.contributions:
                module, symbol = descriptor.implementation.split(":")
                implementation = getattr(importlib.import_module(module), symbol)(
                    descriptor
                )
                implementations[descriptor.implementation] = implementation
        finally:
            sys.path.remove(str(wheel))
        artifacts.append(
            RuntimeExtensionArtifact.create(
                extension_id=manifest.extension_id,
                artifact_bytes=raw,
                implementations=implementations,
            )
        )
    result = tuple(artifacts)
    load_runtime_extensions(
        path,
        artifacts=result,
        runtime_version="0.1.0",
        verification_key_id=env["EXTENSION_KEY_ID"],
        verification_key=key.encode(),
    )
    return result
