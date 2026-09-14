"""Independent clean Docker consumers; build-side orchestration only."""

from pathlib import Path
import hashlib
import json
import subprocess
import time
import uuid

from infra.enterprise.acceptance.fixtures import create, write, workspace_command
from infra.enterprise.bundle.verify import extract

from infra.enterprise.acceptance.report import CHECKS


def require(value, code):
    if not value:
        raise ValueError(code)


class Consumer:
    def __init__(self, directory, bundle, candidate, image, mode, records):
        self.directory, self.bundle, self.candidate = directory, bundle, candidate
        self.mode, self.records = mode, records
        self.name = "p828-" + mode + "-" + uuid.uuid4().hex[:10]
        self.project = "p828-" + mode
        self.slot = "slot"
        self.port = 18428
        self.commands = []
        self.request = create(directory / self.slot)
        self.raw_request = self.request
        self.image = image

    def run(self, args, *, ok=True, timeout=240, input=None):
        from tests.enterprise.configuration_fixtures import CANARY

        r = subprocess.run(args, input=input, capture_output=True, timeout=timeout)
        self.commands.append(
            {
                "argv": args,
                "exit_code": r.returncode,
                "stdout_sha256": hashlib.sha256(r.stdout).hexdigest(),
                "stderr_sha256": hashlib.sha256(r.stderr).hexdigest(),
            }
        )
        require(CANARY.encode() not in r.stdout + r.stderr, "SECRET_CANARY_LEAK")
        if ok and r.returncode:
            # Only stable deployment codes may leave raw diagnostic output.
            import re

            codes = re.findall(rb'"code":\s*"([A-Z_]+)"', r.stdout + r.stderr)
            raise ValueError(
                "CONSUMER_COMMAND_FAILED:" + ",".join(c.decode() for c in codes)
            )
        return r

    def shell(self, *args, **kw):
        return self.run(["docker", "exec", self.name, *args], **kw)

    def docker(self, *args, **kw):
        return self.shell("docker", *args, **kw)

    def record(self, check, **details):
        self.records.append(
            {"name": self.mode + "-" + check, "status": "PASS", **details}
        )
        print("PASS " + self.mode + "-" + check, flush=True)

    def invoke(
        self, action, *extra, slot=None, project=None, port=None, mode=None, **kw
    ):
        return self.shell(
            "sh",
            "/bundle/scripts/" + action + ".sh",
            "/bundle",
            self.candidate["checksums_sha256"],
            self.candidate["images"]["runtime"]["image_id"],
            "/audit/" + (slot or self.slot),
            project or self.project,
            str(port or self.port),
            mode or self.mode,
            *extra,
            **kw,
        )

    def start(self):
        self.run(
            [
                "docker",
                "run",
                "-d",
                "--privileged",
                "--network",
                "none",
                "--name",
                self.name,
                "--label",
                "plantnexus.task=P8-28",
                "--mount",
                f"type=bind,src={self.bundle},dst=/bundle,readonly",
                "--mount",
                f"type=bind,src={self.directory},dst=/audit",
                self.image,
                "dockerd",
                "--storage-driver=overlay2",
                "--host=unix:///var/run/docker.sock",
            ]
        )
        info = {}
        for _ in range(60):
            r = self.docker("info", "--format", "{{json .}}", ok=False, timeout=10)
            try:
                info = json.loads(r.stdout)
            except ValueError:
                info = {}
            if info.get("ServerVersion") and not info.get("ServerErrors"):
                break
            time.sleep(1)
        require(
            info.get("ServerVersion") == "27.5.1" and not info.get("ServerErrors"),
            "CLEAN_DAEMON_UNAVAILABLE",
        )
        require(
            not self.docker("image", "ls", "-q").stdout.strip(), "NONEMPTY_IMAGE_STORE"
        )
        self.shell(
            "sh",
            "-c",
            'for x in python python3 uv npm; do if command -v "$x"; then exit 1; fi; done',
        )
        require(
            not any(
                line.startswith(b"default ")
                for line in self.shell("ip", "route").stdout.splitlines()
            ),
            "OUTBOUND_ROUTE",
        )
        outer = json.loads(self.run(["docker", "inspect", self.name]).stdout)[0]
        require(outer["HostConfig"]["NetworkMode"] == "none", "OUTER_NETWORK")
        require(
            {m["Destination"] for m in outer["Mounts"]}
            == {"/bundle", "/audit", "/var/lib/docker"},
            "UNEXPECTED_MOUNT",
        )
        self.record(
            "clean-store-offline",
            engine=info["ServerVersion"],
            daemon_id=info["ID"],
            initial_images=0,
            consumer_image=outer["Image"],
            network="none",
            host_python=False,
            checkout=False,
            tool_inventory=self.shell("apk", "info", "-v").stdout.decode().splitlines(),
        )

    def external_dependencies(self):
        network = self.project + "-runtime"
        self.docker(
            "network",
            "create",
            "--internal",
            "--label",
            "com.docker.compose.network=runtime",
            "--label",
            "com.docker.compose.project=" + self.project,
            network,
        )
        images = self.candidate["images"]
        for role in ("database", "redis"):
            self.docker(
                "load", "--input", "/bundle/images/" + role + ".tar", timeout=240
            )
        self.docker(
            "run",
            "-d",
            "--name",
            "external-database",
            "--network",
            network,
            "--network-alias",
            "database",
            "--mount",
            "type=bind,src=/audit/slot/secrets,dst=/run/secrets,readonly",
            "-e",
            "POSTGRES_USER_FILE=/run/secrets/db_user",
            "-e",
            "POSTGRES_PASSWORD_FILE=/run/secrets/db_password",
            "-e",
            "POSTGRES_DB=synthetic_test",
            images["database"]["image_id"],
        )
        self.docker(
            "run",
            "-d",
            "--name",
            "external-redis",
            "--network",
            network,
            "--network-alias",
            "redis",
            "--mount",
            "type=bind,src=/audit/slot/secrets,dst=/run/secrets,readonly",
            "--mount",
            "type=bind,src=/bundle/compose/redis-entrypoint.sh,dst=/entrypoint.sh,readonly",
            "--entrypoint",
            "/bin/sh",
            images["redis"]["image_id"],
            "/entrypoint.sh",
        )
        r = None
        for _ in range(60):
            r = self.docker(
                "exec",
                "external-database",
                "sh",
                "-c",
                'pg_isready -q -U "$(cat /run/secrets/db_user)" -d "$POSTGRES_DB"',
                ok=False,
            )
            if r.returncode == 0:
                break
            time.sleep(1)
        require(r is not None and r.returncode == 0, "EXTERNAL_DATABASE_NOT_READY")

    def python(self, code, *, project=None):
        return self.docker(
            "exec", (project or self.project) + "-api-1", "python", "-c", code
        ).stdout

    def http(
        self,
        path,
        *,
        body=None,
        identity: str | None = "headless",
        status=200,
        content_type="application/json",
        command=None,
        port=None,
    ):
        from tests.enterprise.configuration_fixtures import CANARY

        key = uuid.uuid4().hex
        headers = {
            "Content-Type": content_type,
            "X-Correlation-Id": "p828-" + key,
            "Idempotency-Key": "p828-" + key,
        }
        if identity:
            suffix = "-token" if identity == "headless" else "-workspace-" + identity
            headers["Authorization"] = "Bearer " + CANARY + suffix
        if isinstance(body, dict) and "idempotency_key" in body:
            headers["Idempotency-Key"] = body["idempotency_key"]
            headers["X-Correlation-Id"] = body["correlation_id"]
        for field, header in [
            ("tenant_id", "X-APS-Tenant-Id"),
            ("factory_id", "X-APS-Factory-Id"),
            ("planning_scope_id", "X-APS-Planning-Scope-Id"),
        ]:
            headers[header] = self.raw_request["requested_scope"][field]
        if command:
            headers["X-Correlation-Id"] = command["correlation_id"]
            headers["Idempotency-Key"] = command["idempotency_key"]
        hp = self.directory / "headers.private"
        hp.write_text(
            "".join(k + ": " + v + "\n" for k, v in headers.items()),
            encoding="utf-8",
            newline="\n",
        )
        port = port or self.port
        args = [
            "curl",
            "--silent",
            "--show-error",
            "--noproxy",
            "*",
            "--cacert",
            "/audit/slot/config/tls.crt",
            "--resolve",
            f"aps.example.invalid:{port}:127.0.0.1",
            "--max-time",
            "20",
            "--header",
            "@/audit/headers.private",
            "--write-out",
            "\n%{http_code}",
        ]
        if body is not None:
            raw = (
                body
                if isinstance(body, bytes)
                else json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
            )
            (self.directory / "request.private").write_bytes(raw)
            args += ["--request", "POST", "--data-binary", "@/audit/request.private"]
        r = self.shell(*args, f"https://aps.example.invalid:{port}" + path)
        raw, code = r.stdout.rsplit(b"\n", 1)
        require(
            int(code) == status,
            "HTTP_STATUS_" + str(status) + "_OBSERVED_" + code.decode() + "_" + path,
        )
        return json.loads(raw) if raw else {}

    def identity(self):
        descriptors = []
        for role in ("api", "worker"):
            observed = json.loads(
                self.docker("inspect", self.project + "-" + role + "-1").stdout
            )[0]
            require(
                observed["Image"] == self.candidate["images"]["runtime"]["image_id"],
                "IMAGE_MISMATCH",
            )
            descriptors.append(
                json.loads(
                    self.docker(
                        "exec",
                        self.project + "-" + role + "-1",
                        "cat",
                        "/tmp/runtime-descriptor.json",
                    ).stdout
                )
            )
        require(descriptors[0] == descriptors[1], "DESCRIPTOR_MISMATCH")
        d = descriptors[0]["descriptor"]
        resolution = d["runtime_resolution"]
        require(
            resolution["developer_kit_version"] == "1.0.0"
            and d["extension_adapter"]["extension_count"] == 1,
            "KIT_EXTENSION_MISSING",
        )
        self.record(
            "identity",
            image_id=self.candidate["images"]["runtime"]["image_id"],
            descriptor=descriptors[0],
        )

    def check(self):
        self.start()
        if self.mode == "enterprise":
            self.external_dependencies()
        self.invoke("install", timeout=360)
        loaded = sorted(
            set(self.docker("image", "ls", "--no-trunc", "-q").stdout.decode().split())
        )
        require(
            loaded == sorted(v["image_id"] for v in self.candidate["images"].values()),
            "LOADED_IMAGE_SET_MISMATCH",
        )
        self.record("install", images=loaded)
        self.invoke("install", timeout=360)
        heads = json.loads(
            self.python(
                "from bootstrap.services import prepare,CONFIG,database;from sqlalchemy import text;import json;e=database(prepare(CONFIG));c=e.connect();print(json.dumps(list(c.execute(text('SELECT version_num FROM alembic_version')).scalars())));c.close();e.dispose()"
            )
        )
        require(
            heads == ["0009_host_authorization_audit"], "ACTUAL_MIGRATION_HEAD_MISMATCH"
        )
        self.record("repeat-migration", heads=heads)
        self.identity()
        for route in ("live", "ready"):
            self.http("/health/" + route)
        self.record("tls-health", loopback_port=self.port, certificate_verified=True)
        accepted = self.http("/api/v1/planning-runs", body=self.request, status=202)
        run = accepted["accepted"]["planning_run"]["planning_run_id"]
        result = {}
        for _ in range(90):
            result = self.http("/api/v1/planning-runs/" + run + "/status")
            if result["terminal"]:
                break
            time.sleep(1)
        require(result["state"] == "COMPLETED", "PLANNING_NOT_COMPLETED")
        result = self.http("/api/v1/planning-runs/" + run + "/result")
        required = {
            "snapshot",
            "problem",
            "planning_solution",
            "solver_report",
            "validation_report",
            "schedule_version",
        }
        require(required <= set(result["artifacts"]), "ARTIFACT_CLOSURE_MISSING")
        self.record(
            "headless-chain",
            state=result["state"],
            artifacts=result["artifacts"],
            runtime_resolution=result["runtime_resolution"],
        )
        self.http("/api/v1/planning-runs", body=self.request, identity=None, status=401)
        self.http(
            "/api/v1/planning-runs",
            body=b"order,qty\nsynthetic,1",
            content_type="text/csv",
            status=415,
        )
        self.http("/api/v1/planning-runs", body=b'{"a":1,"a":2}', status=400)
        self.record("input-and-identity-negatives")
        sid = result["artifacts"]["schedule_version"]["artifact_id"]
        path = "/api/v1/schedule-versions/" + sid
        self.http(path, identity="headless", status=401)
        schedule = self.http(path, identity="operator")
        self.http(path, identity="limited", status=403)
        self.http(
            "/api/v1/export-jobs/synthetic-unknown/download",
            identity="limited",
            status=403,
        )
        audit = self.python(
            "from pathlib import Path;print(Path('/home/plantnexus/workspace-authorization.jsonl').read_text())"
        )
        reasons = {json.loads(line)["reason"] for line in audit.splitlines() if line}
        require(
            {"RESOURCE_SCOPE_DENIED", "CAPABILITY_DENIED", "INVALID_AUTHENTICATION"}
            <= reasons,
            "DENIAL_AUDIT_MISSING",
        )
        self.record(
            "capability-scope-audit",
            reasons=sorted(reasons),
            audit_sha256=hashlib.sha256(audit).hexdigest(),
        )
        for kind, capability, target, payload, suffix in [
            ("APPROVE", "approve", "WORKSPACE_INTERNAL", {}, "approve"),
            (
                "PUBLISH",
                "publish",
                "SIMULATION_INTERNAL",
                {"previous_current_version": None},
                "publish",
            ),
            (
                "REQUEST_EXPORT",
                "export",
                "SIMULATION_INTERNAL",
                {"package_profile": "p3-standard-export.v1"},
                "exports",
            ),
        ]:
            cmd = workspace_command(
                schedule,
                kind,
                capability,
                target,
                "p828-" + self.mode + "-" + suffix + "-0001",
                payload,
            )
            value = self.http(
                path + "/" + suffix,
                body=cmd,
                identity="operator",
                status=202 if suffix == "exports" else 200,
                command=cmd,
            )
            schedule = self.http(path, identity="operator")
        export_id = value["export_job_id"]
        exported = self.http("/api/v1/export-jobs/" + export_id, identity="operator")
        replay = self.http(
            path + "/exports", body=cmd, identity="operator", status=202, command=cmd
        )
        require(
            replay["export_job_id"] == export_id and schedule["state"] == "PUBLISHED",
            "WORKSPACE_CHAIN_FAILED",
        )
        self.record(
            "workspace-read-approve-publish-export",
            schedule_state=schedule["state"],
            export_job_id=export_id,
            export_state=exported.get("state"),
            scope="existing export creation/read/idempotency; no external delivery",
        )
        self.formal_validator()
        self.negatives()
        self.invoke("stop")
        self.invoke("start", timeout=360)
        require(
            self.http(path, identity="operator")["state"] == "PUBLISHED",
            "RESTART_DATA_LOST",
        )
        require(
            self.http("/api/v1/planning-runs/" + run + "/result")["run_fingerprint"]
            == result["run_fingerprint"],
            "RESTART_RUN_CHANGED",
        )
        self.record("restart-persistence")
        self.recovery(path, export_id)
        self.invoke("logs")
        for role in ("api", "worker"):
            self.docker("logs", self.project + "-" + role + "-1")
        self.record(
            "canary", command_count=len(self.commands), raw_secrets_in_report=False
        )

    def formal_validator(self):
        args = [
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--user",
            "10001:10001",
            "--mount",
            "type=bind,src=/bundle/scripts/bootstrap,dst=/opt/enterprise/bootstrap,readonly",
            "--mount",
            "type=bind,src=/audit/slot/config,dst=/etc/plantnexus,readonly",
            "--workdir",
            "/opt/enterprise",
            "--entrypoint",
            "python",
            self.candidate["images"]["runtime"]["image_id"],
            "-c",
            "from bootstrap.services import validate_inputs;validate_inputs()",
        ]
        self.docker(*args)
        p = self.directory / "slot/config/validation/candidate.json"
        raw = p.read_bytes()
        v = json.loads(raw)
        v["assignments"] = []
        write(p, v)
        try:
            require(
                self.docker(*args, ok=False).returncode != 0,
                "INVALID_SCHEDULE_ACCEPTED",
            )
        finally:
            p.write_bytes(raw)
        self.record(
            "formal-validator", independent=True, network="none", negative_rejected=True
        )

    def negatives(self):
        env = self.directory / "slot/config/deployment.env"
        original = env.read_bytes()
        lock = self.directory / "slot/config/extension-lock.json"
        lock_raw = lock.read_bytes()
        try:
            for mutation in ("missing", "kit", "extension"):
                if mutation == "missing":
                    env.write_bytes(
                        b"\n".join(
                            line
                            for line in original.splitlines()
                            if not line.startswith(b"DB_HOST=")
                        )
                        + b"\n"
                    )
                if mutation == "kit":
                    env.write_bytes(
                        original.replace(b"KIT_VERSION=1.0.0", b"KIT_VERSION=0.0.0")
                    )
                if mutation == "extension":
                    v = json.loads(lock_raw)
                    v["kit_fingerprint"] = "sha256:" + "0" * 64
                    write(lock, v)
                require(
                    self.invoke("preflight", ok=False).returncode != 0,
                    "BAD_CONFIGURATION_ACCEPTED",
                )
                env.write_bytes(original)
                lock.write_bytes(lock_raw)
        finally:
            env.write_bytes(original)
            lock.write_bytes(lock_raw)
        self.record("config-kit-extension-negatives")

    def recovery(self, schedule_path, export_id):
        # Both source modes use fresh standalone recovery targets with identical
        # synthetic endpoint/configuration bytes and a new DB/Redis each time.
        self.invoke("backup", "/audit/backup", "QUIESCE-" + self.project, timeout=360)
        # Backup directories are root-owned mode 0700 on Linux. Read through
        # the consumer without weakening permissions for the build-side user.
        digest = hashlib.sha256(
            self.shell("cat", "/audit/backup/SHA256SUMS").stdout
        ).hexdigest()
        for action, port in [("restore", 18429), ("rollback", 18430)]:
            slot = action
            project = "p828-" + action
            self.shell("cp", "-a", "/audit/slot", "/audit/" + slot)
            if action == "rollback":
                # A prior exact validated slot receipt is required, not invented.
                self.shell("test", "-f", "/audit/" + slot + "/validated.json")
            self.invoke(
                action,
                "/audit/backup",
                digest,
                "TARGET-" + project,
                slot=slot,
                project=project,
                port=port,
                mode="standalone",
                timeout=360,
            )
            require(
                self.http(schedule_path, identity="operator", port=port)["state"]
                == "PUBLISHED",
                "RESTORED_STATE_MISSING",
            )
            require(
                self.http(
                    "/api/v1/export-jobs/" + export_id, identity="operator", port=port
                )["export_job_id"]
                == export_id,
                "RESTORED_EXPORT_MISSING",
            )
            original = self.shell("cat", "/audit/backup/workspace-audit.jsonl").stdout
            restored = self.python(
                "from pathlib import Path;import sys;sys.stdout.buffer.write(Path('/home/plantnexus/workspace-authorization.jsonl').read_bytes())",
                project=project,
            )
            require(original == restored, "RESTORED_AUDIT_CHANGED")
            self.invoke(
                "stop", slot=slot, project=project, port=port, mode="standalone"
            )
            self.record(
                "backup-restore" if action == "restore" else "same-version-rollback",
                backup_checksums_sha256=digest,
            )
        self.invoke("start", timeout=360)

    def stop(self):
        self.run(["docker", "stop", "--timeout", "15", self.name], ok=False, timeout=45)


def execute(bundle_report, report_path, development=False):
    root = Path(__file__).resolve().parents[3]
    source = json.loads(bundle_report.read_text(encoding="utf-8"))
    commit = (
        subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root).decode().strip()
    )
    require(source["code_commit"] == commit, "BUNDLE_CODE_SHA_MISMATCH")
    run_dir = report_path.parent / ("clean-" + uuid.uuid4().hex[:10])
    run_dir.mkdir(parents=True)
    archive = root / source["archive"]
    candidate = extract(archive, source["archive_sha256"], run_dir / "unpacked")
    require(candidate["packaging_commit"] == commit, "CANDIDATE_CODE_SHA_MISMATCH")
    for key in (
        "archive_sha256",
        "payload_fingerprint",
        "manifest_sha256",
        "checksums_sha256",
        "images",
    ):
        require(candidate[key] == source[key], "CANDIDATE_REPORT_MISMATCH")
    bundle = run_dir / "unpacked" / candidate["root"]
    manifest = json.loads((bundle / "MANIFEST.json").read_text(encoding="utf-8"))
    require(development or manifest.get("dirty") is False, "DIRTY_CANDIDATE")
    require(
        (bundle / "scripts/bootstrap/workspace.py").is_file(),
        "WORKSPACE_BINDING_MISSING",
    )
    image = "plantnexus-p828-consumer:" + uuid.uuid4().hex[:12]
    subprocess.run(
        [
            "docker",
            "build",
            "--platform",
            "linux/amd64",
            "-t",
            image,
            str(root / "infra/enterprise/acceptance"),
        ],
        check=True,
    )
    records = []
    commands = []
    errors = []
    consumers = []
    try:
        for mode in ("standalone", "enterprise"):
            directory = run_dir / mode
            directory.mkdir()
            consumer = Consumer(
                directory.resolve(), bundle.resolve(), candidate, image, mode, records
            )
            consumers.append(consumer.name)
            try:
                consumer.check()
            finally:
                consumer.stop()
                commands.extend(consumer.commands)
    except Exception as e:
        errors.append(str(e) if isinstance(e, ValueError) else type(e).__name__)
    expected = {
        mode + "-" + name for mode in ("standalone", "enterprise") for name in CHECKS
    }
    actual = {r["name"] for r in records}
    for name in sorted(expected - actual):
        records.append({"name": name, "status": "BLOCKED"})
    passed = not errors and actual == expected
    report = {
        "schema_version": "enterprise-clean-acceptance.v1",
        "task_id": "TASK-P8-28",
        "code_commit": commit,
        "status": "PASS" if passed else "FAIL",
        "verdict": ("LOCAL_READY" if development else "READY") if passed else "BLOCKED",
        "development": development,
        "production_ready": False,
        "candidate": candidate,
        "checks": records,
        "commands": commands,
        "issues": errors,
        "consumers": consumers,
        "preservation": "stopped; containers and data retained",
        "expected_check_count": len(expected),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    require(passed, "CLEAN_ACCEPTANCE_FAILED:" + ",".join(errors))
    return report
