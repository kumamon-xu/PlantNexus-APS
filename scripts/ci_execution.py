"""Dependency-free CI selection and same-run evidence verification.

Only proven frontend-only edits narrow the initial implementation. Shared,
deleted, renamed, unknown and dependency paths select all current checks.
Historical phase audits are an explicit workflow_dispatch choice.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
from typing import Any
import xml.etree.ElementTree as ET

from scripts.ci_validation_profile import (
    DOCS_ONLY, GitRepository, classify_repository,
)

VERSION = "ci-execution-plan.v1"
JOBS = ("docs_validation", "full_preflight", "full_backend", "frontend_validation",
        "solver_validation", "full_operations", "full_validation")
CURRENT = ("full_preflight", "full_backend", "frontend_validation",
           "solver_validation", "full_operations")
ARTIFACTS: dict[str, str] = dict(zip(JOBS, ("public-docs", "preflight", "backend", "frontend",
                           "solver", "operations", "evidence"), strict=True))


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def plan(root: Path, base: str, head: str, audit: bool = False) -> dict[str, Any]:
    repository = GitRepository(root)
    classification = classify_repository(repository, base, head)
    # An invalid base may widen coverage, but an unidentified head cannot produce evidence.
    resolved_head = repository.resolve_commit(head)
    trusted = all(c.get("passed") for c in classification.checks
                  if c["check"] in {"commit-identities", "base-is-ancestor"})
    paths = [p for e in classification.entries for p in e.paths]
    frontend_only = bool(paths) and trusted and all(
        e.status in {"A", "M"} for e in classification.entries
    ) and all(p.startswith(("frontend/src/", "frontend/tests/", "frontend/e2e/"))
              and p.endswith((".ts", ".tsx", ".css")) for p in paths)
    if frontend_only:
        frontend_only = all(repository.object_mode(resolved_head, p) in {("100644", "blob"), ("100755", "blob")} for p in paths)
    if audit:
        selected, reason = ("full_preflight", "full_backend", "full_operations", "full_validation"), "explicit phase audit; audit job owns frontend and contract coverage"
    elif classification.profile == DOCS_ONLY:
        selected, reason = ("docs_validation",), classification.reason
    elif frontend_only:
        selected, reason = ("full_preflight", "frontend_validation"), "proven frontend-only source/test edits"
    else:
        selected, reason = CURRENT, "shared, dependency, unknown or unproven impact: all current checks"
    payload: dict[str, Any] = {
        "schema_version": VERSION, "head_sha": resolved_head,
        "base_sha": classification.base_sha, "audit": audit,
        "profile": "FULL" if audit else classification.profile,
        "selected": list(selected), "reason": reason,
        "expected_jobs": {"classify": "success", **{
            j: "success" if j in selected else "skipped" for j in JOBS}, "validate": "success"},
        "artifact_prefixes": ["profile", *[ARTIFACTS[j] for j in selected], "aggregate"],
    }
    payload["plan_digest"] = digest(payload)
    return payload


def validate_plan(value: dict[str, Any], head: str) -> None:
    unsigned = {k: v for k, v in value.items() if k != "plan_digest"}
    if value.get("schema_version") != VERSION or value.get("head_sha") != head:
        raise ValueError("plan version/SHA mismatch")
    if value.get("plan_digest") != digest(unsigned):
        raise ValueError("plan digest mismatch")
    selected = value.get("selected")
    if not isinstance(selected, list) or not selected or len(set(selected)) != len(selected) or set(selected) - set(JOBS):
        raise ValueError("invalid selected jobs")
    expected = {"classify": "success", **{j: "success" if j in selected else "skipped" for j in JOBS}, "validate": "success"}
    if value.get("expected_jobs") != expected:
        raise ValueError("inconsistent expected jobs")
    if value.get("artifact_prefixes") != ["profile", *[ARTIFACTS[j] for j in selected], "aggregate"]:
        raise ValueError("inconsistent artifact selection")
    if ("full_validation" in selected) != (value.get("audit") is True):
        raise ValueError("audit selection mismatch")


def identity() -> dict[str, str]:
    value = {key: os.environ.get(env, "") for key, env in (
        ("head_sha", "GITHUB_SHA"), ("run_id", "GITHUB_RUN_ID"),
        ("run_attempt", "GITHUB_RUN_ATTEMPT"))}
    if not re.fullmatch(r"[0-9a-f]{40}", value["head_sha"]) or not all(
        value[k].isdigit() for k in ("run_id", "run_attempt")
    ):
        raise ValueError("missing exact CI run identity")
    return value


def check_report(path: Path) -> None:
    """A successful producer must also emit successful machine evidence."""
    if path.suffix == ".json":
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"report is not an object: {path}")
        if value.get("result") == "FAIL" or value.get("status") == "FAIL" or any(
            value.get(k) for k in ("issues", "blocking_gaps", "blocking_issues")
        ):
            raise ValueError(f"report records failure: {path}")
    elif path.suffix == ".xml":
        text = path.read_text(encoding="utf-8")
        if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
            raise ValueError("DTD/entity is forbidden in JUnit")
        tree = ET.fromstring(text)
        suites = list(tree.iter("testsuite"))
        if not suites or sum(int(s.get("tests", "0")) - int(s.get("skipped", "0")) for s in suites) <= 0:
            raise ValueError(f"JUnit has no executed tests: {path}")
        if any(int(s.get(k, "0")) for s in suites for k in ("errors", "failures")) or list(tree.iter("failure")) or list(tree.iter("error")):
            raise ValueError(f"JUnit records failure: {path}")


def prepare_runtime(root: Path) -> dict[str, Any]:
    """Stage only frozen packaging README in an ephemeral Actions checkout.

    The operations target deliberately describes a historical Runtime build.
    Current source/Schema/lock drift is still rejected, never restored away.
    """
    from scripts.p8_operations_check import RUNTIME_INPUTS, TARGET_PATH

    run_identity = identity()
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise ValueError("runtime preparation is restricted to ephemeral Actions checkouts")
    repository = GitRepository(root)
    if repository.run("rev-parse", "HEAD").stdout.strip() != run_identity["head_sha"]:
        raise ValueError("checkout does not match run identity")
    target = json.loads((root / TARGET_PATH).read_text(encoding="utf-8"))
    source = repository.resolve_commit(target["release"]["implementation_sha"])
    if repository.run("diff", "HEAD", "--", "README.md").stdout:
        raise ValueError("refusing to overwrite local README changes")
    changed = repository.run("diff", "--name-only", source, "--", *RUNTIME_INPUTS).stdout.splitlines()
    untracked = repository.run("ls-files", "--others", "--exclude-standard", "--", *RUNTIME_INPUTS).stdout
    if set(changed) - {"README.md"} or untracked:
        raise ValueError("Runtime source drift; only frozen packaging README may be staged")
    before = hashlib.sha256((root / "README.md").read_bytes()).hexdigest()
    repository.run("restore", "--source", source, "--worktree", "--", "README.md")
    if repository.run("diff", "--name-only", source, "--", *RUNTIME_INPUTS).stdout:
        raise ValueError("frozen Runtime inputs remain inconsistent")
    return {"schema_version": "ci-runtime-preparation.v1", "result": "PASS", **run_identity,
            "runtime_source_sha": source, "packaging_metadata": "README.md",
            "current_readme_sha256": before,
            "target_readme_sha256": hashlib.sha256((root / "README.md").read_bytes()).hexdigest(),
            "restored_product_paths": [], "issues": []}


def seal(root: Path, job: str, files: list[Path]) -> dict[str, Any]:
    if job not in JOBS or not files:
        raise ValueError("unknown job or empty evidence")
    records = []
    for path in files:
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"missing or empty evidence: {path}")
        check_report(path)
        records.append({"name": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return {"schema_version": "ci-evidence-seal.v1", **identity(), "job": job,
            "environment": {"os": platform.system(), "python": platform.python_version()},
            "inputs": {str(p): hashlib.sha256((root / p).read_bytes()).hexdigest()
                       for p in ("uv.lock", "frontend/package-lock.json", ".github/workflows/ci.yml")},
            "files": records}


def verify_seal(root: Path, downloads: Path, job: str) -> dict[str, Any]:
    matches = list(downloads.rglob(f"ci-seal-{job}.json"))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one seal for {job}, found {len(matches)}")
    value = json.loads(matches[0].read_text(encoding="utf-8"))
    if value.get("schema_version") != "ci-evidence-seal.v1" or value.get("job") != job:
        raise ValueError("invalid evidence seal")
    if any(value.get(k) != v for k, v in identity().items()):
        raise ValueError("evidence run/SHA/attempt mismatch")
    if value.get("environment") != {"os": platform.system(), "python": platform.python_version()}:
        raise ValueError("evidence environment mismatch")
    expected_inputs = seal(root, job, [root / "uv.lock"])["inputs"]
    if value.get("inputs") != expected_inputs or not value.get("files"):
        raise ValueError("evidence inputs mismatch or missing records")
    for record in value["files"]:
        if Path(record["name"]).name != record["name"]:
            raise ValueError("unsafe evidence name")
        candidates = list(downloads.rglob(record["name"]))
        if not candidates or any(hashlib.sha256(p.read_bytes()).hexdigest() != record["sha256"] for p in candidates):
            raise ValueError(f"missing or corrupted evidence: {record['name']}")
        for candidate in candidates:
            check_report(candidate)
    return value


def aggregate(root: Path, value: dict[str, Any], needs: dict[str, Any], downloads: Path) -> dict[str, Any]:
    validate_plan(value, identity()["head_sha"])
    for job, expected in value["expected_jobs"].items():
        if job == "validate":
            continue
        if needs.get(job, {}).get("result") != expected:
            raise ValueError(f"{job}: expected {expected}, observed {needs.get(job)}")
    seals = [verify_seal(root, downloads, job) for job in value["selected"]]
    return {"schema_version": "ci-aggregate.v1", "result": "PASS", **identity(),
            "plan_digest": value["plan_digest"], "selected": value["selected"],
            "seals": seals, "issues": []}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "seal", "aggregate", "verify-shared", "prepare-runtime"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--base", default=os.environ.get("PLANTNEXUS_CI_CHANGE_BASE", ""))
    parser.add_argument("--head", default=os.environ.get("GITHUB_SHA", ""))
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--job", choices=JOBS)
    parser.add_argument("--files", nargs="+", type=Path)
    parser.add_argument("--downloads", type=Path, default=Path("build/downloads"))
    args = parser.parse_args()
    if args.command == "plan":
        value = plan(args.root, args.base, args.head, args.audit)
        output = os.environ.get("GITHUB_OUTPUT")
        if output:
            with Path(output).open("a", encoding="utf-8") as stream:
                stream.write(f"profile={value['profile']}\n")
                for job in JOBS:
                    stream.write(f"{job}={str(job in value['selected']).lower()}\n")
    elif args.command == "prepare-runtime":
        value = prepare_runtime(args.root)
    elif args.command == "seal":
        value = seal(args.root, args.job, args.files or [])
    elif args.command == "verify-shared":
        value = verify_seal(args.root, args.downloads, args.job)
    else:
        value = plan(args.root, args.base, args.head, args.audit)
        plans = list(args.downloads.rglob("ci-execution-plan.json"))
        if len(plans) != 1 or json.loads(plans[0].read_text(encoding="utf-8")) != value:
            raise ValueError("missing or inconsistent execution plan")
        value = aggregate(args.root, value, json.loads(os.environ["CI_NEEDS"]), args.downloads)
    if args.report:
        write(args.report, value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
