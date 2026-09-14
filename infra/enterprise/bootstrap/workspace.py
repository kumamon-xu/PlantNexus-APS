"""Explicit TEST workspace identity and append-only, durable denial evidence."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import stat
from threading import Lock

CAPABILITIES = frozenset(
    {"view", "edit", "lock", "approve", "reject", "publish", "export", "audit"}
)
SCOPES = ("planning_run_scope", "schedule_version_scope", "export_job_scope")


def validate(document):
    """No defaults, roles, wildcard expansion, or client-derived grants."""
    from .preflight import fail

    def require(value):
        if not value:
            fail("authorization", "WORKSPACE_POLICY_INVALID")

    require(
        isinstance(document, dict)
        and set(document)
        == {
            "policy_version",
            "policy_id",
            "environment",
            "data_plane",
            "production_binding",
            "principals",
        }
    )
    require(document["policy_version"] == "enterprise-workspace-authorization.v1")
    require(
        document["environment"] == "TEST"
        and document["data_plane"] == "SIMULATION"
        and document["production_binding"] is False
    )
    require(
        isinstance(document["policy_id"], str)
        and re.fullmatch(r"[A-Za-z0-9._:-]{1,256}", document["policy_id"])
        and "test" in document["policy_id"].lower()
    )
    require(
        isinstance(document["principals"], list) and len(document["principals"]) <= 32
    )
    actors, tokens = set(), set()
    for p in document["principals"]:
        require(
            isinstance(p, dict)
            and set(p)
            == {
                "actor_ref",
                "token_file",
                "capabilities",
                "allow_all_synthetic_resources",
                *SCOPES,
            }
        )
        require(
            isinstance(p["actor_ref"], str)
            and re.fullmatch(r"actor:[A-Za-z0-9._:-]{1,240}", p["actor_ref"])
        )
        require(p["actor_ref"] not in actors)
        actors.add(p["actor_ref"])
        require(
            isinstance(p["token_file"], str) and Path(p["token_file"]).is_absolute()
        )
        require(p["token_file"] not in tokens)
        tokens.add(p["token_file"])
        require(isinstance(p["allow_all_synthetic_resources"], bool))
        for key in ("capabilities", *SCOPES):
            values = p[key]
            require(isinstance(values, list) and len(values) <= 1024)
            require(
                all(
                    isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9._:*\-]{1,256}", v)
                    for v in values
                )
            )
            require(len(set(values)) == len(values))
            if key == "capabilities":
                require(set(values) <= CAPABILITIES)
            else:
                require(all("*" not in v or v == "*" for v in values))
                require(
                    "*" not in values
                    or (values == ["*"] and p["allow_all_synthetic_resources"])
                )
    return document


class LocalWorkspaceIdentity:
    def __init__(self, policy, tokens):
        self.policy = policy
        self.tokens = tokens

    def resolve(self, bearer_token):
        from app.api.dependencies.authorization import PrincipalContext

        for p, token in zip(self.policy["principals"], self.tokens, strict=True):
            if hmac.compare_digest(bearer_token.encode(), token.encode()):
                return PrincipalContext(
                    actor_ref=p["actor_ref"],
                    resolved_capabilities=frozenset(p["capabilities"]),
                    auth_policy_version=self.policy["policy_id"],
                    production_binding=False,
                    **{key: frozenset(p[key]) for key in SCOPES},
                )
        return None


class DurableDenialAudit:
    """Separate deployment audit volume; failures propagate to the HTTP guard."""

    def __init__(
        self,
        path=Path("/home/plantnexus/workspace-authorization.jsonl"),
        *,
        policy_id,
        policy_fingerprint,
    ):
        self.path = path
        self.policy_id = policy_id
        self.policy_fingerprint = policy_fingerprint
        self.lock = Lock()
        self.append(b"")

    def record(self, event):
        value = asdict(event)
        # HTTP resource/correlation text can be attacker controlled. Persist hashes,
        # not raw IDs, tokens or claims. Capability/reason are server guard values.
        for field in ("correlation_id", "resource_id", "actor_ref"):
            raw = value.pop(field)
            value[field + "_sha256"] = hashlib.sha256((raw or "").encode()).hexdigest()
        value.update(
            audit_version="enterprise-workspace-denial.v1",
            policy_id=self.policy_id,
            policy_fingerprint=self.policy_fingerprint,
            occurred_at_utc=datetime.now(timezone.utc).isoformat(),
        )
        raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
        self.append(raw)

    def append(self, raw):
        with self.lock:
            flags = (
                os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
            )
            fd = os.open(self.path, flags, 0o600)
            try:
                if not stat.S_ISREG(os.fstat(fd).st_mode):
                    raise OSError("Audit regular file required")
                offset = 0
                while offset < len(raw):
                    written = os.write(fd, raw[offset:])
                    if written <= 0:
                        raise OSError("Audit append failed")
                    offset += written
                os.fsync(fd)
            finally:
                os.close(fd)
