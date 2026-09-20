"""Server-bound asynchronous ReplanRequest application.

HTTP prepares immutable inputs and queues identities. Solving belongs to the
Runtime Worker; neither request reads nor controls call a Solver.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from typing import Any, cast

from sqlalchemy import select

from app.application.planning_runs import (
    PlanningRunCancelCommand,
    PlanningRunOrchestrationService,
    PlanningRunAttemptFailureCommand,
    PlanningRunTransitionCommand,
)
from app.application.runtime_dynamic_replanning import RuntimeEventError
from app.data_validation.canonical_ingress import (
    canonical_fingerprint,
    canonical_json_bytes,
    run_fingerprint,
)
from app.domain.execution_contracts import require_p4_document
from app.domain.planning_run import PlanningRunAggregate, PLANNING_RUN_TERMINAL_STATES
from app.domain.planning_run import PlanningRunAttemptStatus
from app.infrastructure.replan_persistence import (
    REPLAN_ATTEMPTS,
    REPLAN_PROJECTION_CHECKPOINTS,
    ReplanAuditAction,
    build_replan_attempt,
    build_replan_audit_record,
)
from app.infrastructure.replan_repository import (
    SqlAlchemyReplanRequestRepository,
    SqlAlchemyReplanLineageRepository,
    SqlAlchemyReplanAuditRepository,
)
from app.infrastructure.runtime_replan_repository import (
    RuntimeReplanRunRepository,
    TransactionEngine,
    serialize_creation,
)
from app.infrastructure.workspace_persistence import WorkspaceDataPlane
from app.planning.problem.builder import build_planning_problem_v2
from app.planning.problem.freeze_projection import project_effective_locks
from app.planning.reporting.kpi import calculate_schedule_kpi_metrics


def artifact(version: str, identity: str, fingerprint: str) -> dict[str, str]:
    return {
        "document_version": version,
        "artifact_id": identity,
        "fingerprint": fingerprint,
    }


class RuntimeReplanApplication:
    def __init__(
        self,
        *,
        engine: Any,
        schemas: Any,
        events: Any,
        schedules: Any,
        publications: Any,
        policy: Any,
        catalog: Any,
        runtime: Any,
        context_binding: Any,
        dispatcher: Any,
        source_kpi: Any,
    ) -> None:
        self.engine, self.schemas, self.events = engine, schemas, events
        self.schedules, self.publications = schedules, publications
        self.policy, self.catalog, self.runtime = deepcopy(policy), catalog, runtime
        self.context_binding, self.dispatcher, self.source_kpi = (
            context_binding,
            dispatcher,
            source_kpi,
        )
        self.plane = WorkspaceDataPlane.SIMULATION
        self.requests = SqlAlchemyReplanRequestRepository(engine, data_plane=self.plane)
        self.lineage = SqlAlchemyReplanLineageRepository(engine, data_plane=self.plane)
        self.audits = SqlAlchemyReplanAuditRepository(engine, data_plane=self.plane)
        self.runs = self.run_repository(engine)
        self.orchestration = self.orchestrator(engine)

    def run_repository(self, engine: Any) -> RuntimeReplanRunRepository:
        return RuntimeReplanRunRepository(
            engine, data_plane=self.plane, verify_source=self.verify_source
        )

    def orchestrator(self, engine: Any) -> PlanningRunOrchestrationService:
        return PlanningRunOrchestrationService(
            repository=self.run_repository(engine), schemas=self.schemas
        )

    def latest(self, request_id: str, connection: Any = None) -> Any:
        if connection is None:
            with self.engine.connect() as conn:
                return self.latest(request_id, conn)
        row = connection.execute(
            select(REPLAN_ATTEMPTS.c.attempt_id)
            .where(
                REPLAN_ATTEMPTS.c.data_plane == "SIMULATION",
                REPLAN_ATTEMPTS.c.request_id == request_id,
            )
            .order_by(REPLAN_ATTEMPTS.c.attempt_number.desc())
        ).first()
        return (
            None
            if row is None
            else self.lineage.get_attempt_in_transaction(connection, row[0])
        )

    def checkpoint(self, connection: Any, document: Any) -> None:
        stream = document["event_stream"]
        # Serialize PostgreSQL projection advancement with request/result commit.
        # SQLite result/create transactions already hold BEGIN IMMEDIATE.
        if connection.dialect.name == "postgresql":
            table = REPLAN_PROJECTION_CHECKPOINTS
            connection.execute(
                select(table)
                .where(
                    table.c.data_plane == "SIMULATION",
                    table.c.factory_id == document["factory_id"],
                    table.c.planning_scope_id == document["planning_scope_id"],
                    table.c.authority_id == stream["authority"]["authority_id"],
                    table.c.stream_id == stream["source_stream"]["stream_id"],
                    table.c.stream_version == stream["source_stream"]["stream_version"],
                )
                .with_for_update()
            ).first()
        self.requests._assert_checkpoint(
            connection,
            candidate=document,
            stream=stream,
            authority=stream["authority"],
            source_stream=stream["source_stream"],
            fact=stream["fact_checkpoint"],
        )

    def prepare(self, document: Any, binding: Any) -> dict[str, Any]:
        if require_p4_document(document) != "replan-request.v1":
            raise RuntimeEventError("INVALID_INPUT", "request")
        if (
            document["factory_id"] != binding["factory_id"]
            or document["planning_scope_id"] != binding["planning_scope_id"]
            or document["environment"] != self.events._environment
        ):
            raise RuntimeEventError("AUTHORIZATION_DENIED", "request.scope")
        source = self.events._source(binding, binding["base_planning_run_id"])
        request_stream = document["event_stream"]["source_stream"]
        if any(
            request_stream[key] != binding[key]
            for key in ("authority_id", "stream_id", "stream_version")
        ):
            raise RuntimeEventError("AUTHORIZATION_DENIED", "request.event_stream")
        snapshot = self.events._snapshots.get_by_id(
            document["new_snapshot"]["artifact_id"]
        )
        if (
            snapshot is None
            or snapshot.snapshot_hash != document["new_snapshot"]["fingerprint"]
        ):
            raise RuntimeEventError("MIXED_LINEAGE", "new_snapshot")
        if document["new_snapshot_cutoff_at_utc"] != snapshot.document["cutoff_at_utc"]:
            raise RuntimeEventError("MIXED_LINEAGE", "snapshot.cutoff")
        cursor, seen = snapshot, set()
        while cursor.snapshot_hash != source.snapshot.snapshot_hash:
            if cursor.snapshot_hash in seen:
                raise RuntimeEventError("MIXED_LINEAGE", "snapshot.predecessor")
            seen.add(cursor.snapshot_hash)
            previous = cursor.document["source_versions"].get(
                "plantnexus-previous-snapshot"
            )
            cursor = (
                None
                if previous is None
                else self.events._snapshots.get_by_hash(previous)
            )
            if cursor is None:
                raise RuntimeEventError("MIXED_LINEAGE", "snapshot.predecessor")
        plan = deepcopy(source.document["build_plan"])
        priorities = plan["priority_facts"]
        stream = self.events._events.list_stream(
            **{k: binding[k] for k in ("authority_id", "stream_id", "stream_version")}
        )
        for event in stream:
            self.events._validate(event, binding)
            if (
                event["source_position"] <= document["event_stream"]["through_position"]
                and event["event_type"] == "URGENT_DEMAND_RECEIVED"
            ):
                payload = event["payload"]
                priorities[payload["demand_order_id"]] = {
                    "priority_weight": payload["priority_weight"],
                    **payload["priority_source"],
                }
        active = {
            v["demand_order_id"] for v in snapshot.document["records"]["demand_orders"]
        }
        plan["priority_facts"] = {k: v for k, v in priorities.items() if k in active}
        plan["horizon_start_utc"] = snapshot.document["cutoff_at_utc"]
        args = {
            k: plan[k]
            for k in (
                "priority_facts",
                "problem_builder_version",
                "tick_seconds",
                "horizon_start_utc",
                "horizon_end_utc",
            )
        }
        problem = build_planning_problem_v2(snapshot, **args)
        if document["new_problem"] != artifact(
            "planning-problem.v2",
            "planning-problem-v2-" + problem.problem_hash[7:],
            problem.problem_hash,
        ):
            raise RuntimeEventError("MIXED_LINEAGE", "new_problem")
        base = self.schedules.get(
            document["base_schedule_version"]["schedule_version_id"]
        )
        current = self.publications.get_current()
        if (
            base is None
            or current is None
            or base["state"] != "PUBLISHED"
            or current.schedule_version_id != base["schedule_version_id"]
            or document["base_schedule_version"]
            != {
                k: base[k]
                for k in (
                    "schedule_version_version",
                    "schedule_version_id",
                    "state",
                    "content_fingerprint",
                )
            }
        ):
            raise RuntimeEventError("STATE_CONFLICT", "base_schedule_version")
        for field in ("snapshot", "problem"):
            key = (
                "new_" + field
                if base["schedule_version_version"] == "schedule-version.v2"
                else field
            )
            if document["base_" + field] != base["lineage"][key]:
                raise RuntimeEventError("MIXED_LINEAGE", "base." + field)
        projection = project_effective_locks(
            snapshot=snapshot, problem=problem, base_schedule=base, policy=self.policy
        ).document
        if base.get("source_kind") in {"MANUAL_EDIT", "LOCK_CHANGE"}:
            projected_locks = {
                item["reference_id"]: {
                    "lock_id": item["reference_id"],
                    "lock_type": kind,
                    **{
                        key: item.get(key)
                        for key in (
                            "operation_id",
                            "resource_id",
                            "start_at_utc",
                            "end_at_utc",
                        )
                    },
                }
                for section, kind in (
                    ("explicit_hard_locks", "HARD"),
                    ("soft_locks", "SOFT"),
                )
                for item in cast(list[dict[str, Any]], projection[section])
            }
            if any(
                projected_locks.get(lock["lock_id"]) != lock
                for lock in base["content"]["locks"]
            ):
                raise RuntimeEventError("MIXED_LINEAGE", "base.locks.fact_projection")
        if (
            document["freeze_resolution"] != projection["freeze_resolution"]
            or document["planning_policy"] != projection["planning_policy"]
        ):
            raise RuntimeEventError("MIXED_LINEAGE", "freeze_policy")
        limits = self.catalog.solve_limits
        limit_reference = {
            k: limits[k]
            for k in (
                "solve_limits_version",
                "limits_id",
                "limits_revision",
                "max_wall_time_seconds",
                "max_workers",
                "random_seed",
            )
        }
        limit_reference["limits_fingerprint"] = canonical_fingerprint(limits)
        if document["solve_limits"] != limit_reference:
            raise RuntimeEventError("MIXED_LINEAGE", "solve_limits")
        kpi, base_problem = self.source_kpi(base)
        if (
            artifact(kpi["kpi_version"], kpi["kpi_id"], canonical_fingerprint(kpi))
            != base["lineage"]["kpi"]
        ):
            raise RuntimeEventError("MIXED_LINEAGE", "base.kpi")
        metrics = calculate_schedule_kpi_metrics(
            base_problem, base["content"]["assignments"]
        )
        if (
            kpi["delivery"] != metrics.delivery_document
            or kpi["planning"] != metrics.planning_document
            or kpi["resources"] != metrics.resource_documents
        ):
            raise RuntimeEventError("MIXED_LINEAGE", "base.kpi.content")
        return {
            "version": "runtime-replan-input.v1",
            "request": deepcopy(document),
            "binding_fingerprint": canonical_fingerprint(binding),
            "source_ingress_id": source.document["ingress_id"],
            "source_record_fingerprint": source.document["record_fingerprint"],
            "source_run": source.document["planning_run"],
            "source_prepared": source.document["prepared_artifacts"],
            "source_provenance": source.document["canonical_request"]["payload"][
                "synthetic_provenance"
            ],
            "snapshot": snapshot.document,
            "problem": problem.document,
            "build_plan": args,
            "policy": deepcopy(self.policy),
            "limits": limits,
            "before_kpi": kpi,
        }

    def verify_source(self, connection: Any, aggregate: PlanningRunAggregate) -> None:
        frozen = aggregate.prepared_artifacts["runtime_replan"]
        scope = aggregate.document["effective_scope"]
        binding = self.events._bindings.get(scope["planning_scope_id"])
        if binding is None:
            raise RuntimeEventError("AUTHORIZATION_DENIED", "replan.binding")
        source = self.events._source(binding, binding["base_planning_run_id"])
        if (
            aggregate.source_ingress_id != source.document["ingress_id"]
            or aggregate.source_record_fingerprint
            != source.document["record_fingerprint"]
            or scope != source.document["effective_scope"]
        ):
            raise RuntimeEventError("MIXED_LINEAGE", "replan.canonical_source")
        self.checkpoint(connection, frozen["request"])

    def _create(self, request: Any, binding: Any, *, retry: bool) -> tuple[Any, bool]:
        command = request.document
        document = cast(
            Any, self.requests.get(request.resource_id) if retry else command
        )
        if document is None:
            raise RuntimeEventError("SOURCE_NOT_FOUND", "request")
        if retry and command["request_fingerprint"] != document["request_fingerprint"]:
            raise RuntimeEventError("MIXED_LINEAGE", "request_fingerprint")
        context, window = self.context_binding(request.context, binding)
        key = request.context.idempotency_key_reference
        if key is None:
            raise RuntimeEventError("INVALID_INPUT", "idempotency_key")
        audit_scope = f"SIMULATION/REPLAN_HTTP/{binding['factory_id']}/{binding['planning_scope_id']}/{'RETRY' if retry else 'CREATE'}"
        with self.engine.begin() as connection:
            receipt = self.audits._find_by_idempotency(
                connection, scope=audit_scope, key_reference=key
            )
            if receipt is not None:
                existing = cast(Any, self.audits._load(receipt))
                if existing["request_fingerprint"] != canonical_fingerprint(command):
                    raise RuntimeEventError("IDEMPOTENCY_CONFLICT", "request")
                attempt = self.lineage.get_attempt_in_transaction(
                    connection, existing["aggregate_id"]
                )
                return attempt, True
        frozen = self.prepare(document, binding)
        with self.engine.begin() as connection:
            serialize_creation(connection, frozen["source_ingress_id"])
            receipt = self.audits._find_by_idempotency(
                connection, scope=audit_scope, key_reference=key
            )
            if receipt is not None:
                existing = cast(Any, self.audits._load(receipt))
                if existing["request_fingerprint"] != canonical_fingerprint(command):
                    raise RuntimeEventError("IDEMPOTENCY_CONFLICT", "request")
                return self.lineage.get_attempt_in_transaction(
                    connection, existing["aggregate_id"]
                ), True
            self.checkpoint(connection, document)
            latest = self.latest(document["request_id"], connection)
            number = 1
            if latest is not None:
                if not retry:
                    raise RuntimeEventError("IDEMPOTENCY_CONFLICT", "request")
                old = self.runs.get(latest["planning_run_id"])
                if (
                    old is None
                    or latest["attempt_id"] != command["expected_attempt_id"]
                    or latest["attempt_number"] != command["expected_attempt_number"]
                    or old.aggregate.document["state"]
                    != command["expected_planning_run_state"]
                    or old.aggregate.document["state"]
                    not in PLANNING_RUN_TERMINAL_STATES
                    or old.aggregate.document["state"] == "COMPLETED"
                ):
                    raise RuntimeEventError("STATE_CONFLICT", "expected_attempt")
                number = latest["attempt_number"] + 1
            elif retry:
                raise RuntimeEventError("SOURCE_NOT_FOUND", "attempt")
            run_id = (
                "planning-run-replan-"
                + canonical_fingerprint(
                    {"request": document["request_fingerprint"], "attempt": number}
                )[7:]
            )
            attempt = build_replan_attempt(
                request_id=document["request_id"],
                request_fingerprint=document["request_fingerprint"],
                planning_run_id=run_id,
                attempt_number=number,
                idempotency_scope=f"SIMULATION/REPLAN/{document['request_id']}",
                idempotency_key_reference=key,
                correlation_id=document["correlation_id"],
                created_at_utc=context.occurred_at_utc,
            )
            frozen["attempt"] = attempt.as_document()
            frozen["created_context"] = asdict(context)
            frozen["created_context"]["capabilities"] = sorted(context.capabilities)
            frozen["fingerprint"] = canonical_fingerprint(frozen)
            run = deepcopy(frozen["source_run"])
            run.update(
                planning_run_version="planning-run.v2", schema_set_version="2.11.0"
            )
            run.update(
                planning_run_id=run_id,
                runtime_resolution=self.runtime,
                created_at_utc=context.occurred_at_utc,
                updated_at_utc=context.occurred_at_utc,
            )
            run["inputs"] = {
                "planning_policy": artifact(
                    "planning-policy.v2",
                    self.policy["policy_id"],
                    canonical_fingerprint(self.policy),
                ),
                "solve_limits": self.catalog.solve_limits_reference,
            }
            prepared = {
                "import_quality_report": frozen["source_prepared"][
                    "import_quality_report"
                ],
                "snapshot": document["new_snapshot"],
                "problem": document["new_problem"],
                "synthetic_provenance": frozen["source_provenance"],
                "runtime_replan": frozen,
            }

            def aggregate() -> PlanningRunAggregate:
                run["run_fingerprint"] = run_fingerprint(run)
                return PlanningRunAggregate(
                    canonical_json_bytes(run),
                    canonical_json_bytes(run),
                    canonical_json_bytes(prepared),
                    frozen["source_ingress_id"],
                    frozen["source_record_fingerprint"],
                )

            scoped = TransactionEngine(self.engine, connection)
            orchestration = self.orchestrator(scoped)
            creation_audit = orchestration._audit(
                aggregate=aggregate(),
                context=context,
                operation="REPLAN_CREATE",
                reason="Create a new run from an immutable ReplanRequest.",
                request_fingerprint=document["request_fingerprint"],
                scope=audit_scope,
                key_reference=key,
                parent_audit_event_id=None,
            )
            prepared["runtime_replan_creation_audit"] = creation_audit
            audit_ref = artifact(
                "audit-event.v1",
                creation_audit["audit_event_id"],
                canonical_fingerprint(creation_audit),
            )
            run["last_transition"] = {
                **run["last_transition"],
                "occurred_at_utc": context.occurred_at_utc,
                "audit": audit_ref,
            }
            run["audit_references"] = [audit_ref]
            self.requests.append_in_transaction(connection, document)
            self.lineage.append_attempt_in_transaction(connection, attempt)
            result = orchestration.materialize_prepared(
                aggregate(),
                context=context,
                key_reference=key,
                available_at_utc=window.available_at_utc,
                timeout_at_utc=window.timeout_at_utc,
            )
            self.audits.append_in_transaction(
                connection,
                build_replan_audit_record(
                    action=ReplanAuditAction.REPLAN_ATTEMPT_LINKED,
                    aggregate_type="REPLAN_ATTEMPT",
                    aggregate_id=attempt.attempt_id,
                    correlation_id=context.correlation_id,
                    idempotency_scope=audit_scope,
                    idempotency_key_reference=key,
                    request_fingerprint=canonical_fingerprint(command),
                    occurred_at_utc=context.occurred_at_utc,
                ),
            )
        if result.work_item is None:
            raise RuntimeEventError("SYSTEM_ERROR", "work_item")
        try:
            self.dispatcher.dispatch(result.work_item.document)
        except Exception:  # noqa: BLE001 - durable command remains queryable after broker failure
            model = self.runs.get(run_id)
            if model is not None and model.attempts[-1].document["status"] == "QUEUED":
                run = model.aggregate.document
                pending = model.attempts[-1].document
                self.orchestration.record_attempt_failure(
                    PlanningRunAttemptFailureCommand(
                        planning_run_id=run_id,
                        expected_revision=run["revision"],
                        expected_state=run["state"],
                        expected_run_fingerprint=run["run_fingerprint"],
                        attempt_id=pending["attempt_id"],
                        attempt_number=1,
                        expected_attempt_revision=pending["revision"],
                        outcome=PlanningRunAttemptStatus.DISPATCH_FAILED,
                        failure_code="DISPATCH_FAILED",
                        idempotency_key="replan-dispatch-"
                        + result.work_item.document["work_item_id"],
                        reason="Broker did not acknowledge dispatch.",
                    ),
                    context=context,
                )
                self.orchestration.transition(
                    PlanningRunTransitionCommand(
                        planning_run_id=run_id,
                        expected_revision=run["revision"],
                        expected_state=run["state"],
                        expected_run_fingerprint=run["run_fingerprint"],
                        to_state="FAILED",
                        idempotency_key="replan-dispatch-terminal-"
                        + result.work_item.document["work_item_id"],
                        attempt_id=pending["attempt_id"],
                        reason="Dispatch failed; an explicit new request attempt is required.",
                        artifacts=run["artifacts"],
                    ),
                    context=context,
                )
        return attempt.as_document(), False

    def _cancel(
        self, request: Any, binding: Any, attempt: Any, document: Any
    ) -> tuple[Any, bool]:
        command = request.document
        context, _ = self.context_binding(request.context, binding)
        key = request.context.idempotency_key_reference
        scope = f"SIMULATION/REPLAN_HTTP/{binding['factory_id']}/{binding['planning_scope_id']}/CANCEL"
        with self.engine.begin() as connection:
            receipt = self.audits._find_by_idempotency(
                connection, scope=scope, key_reference=key
            )
            if receipt is not None:
                previous = self.audits._load(receipt)
                if (
                    previous["request_fingerprint"] != canonical_fingerprint(command)
                    or previous["aggregate_id"] != attempt["attempt_id"]
                ):
                    raise RuntimeEventError("IDEMPOTENCY_CONFLICT", "cancel")
                stored = self.runs.get(attempt["planning_run_id"])
                if stored is None:
                    raise RuntimeEventError("SOURCE_NOT_FOUND", "run")
                return stored.aggregate.document, True
            model = self.runs.get(attempt["planning_run_id"])
            if model is None:
                raise RuntimeEventError("SOURCE_NOT_FOUND", "run")
            run = model.aggregate.document
            if (
                attempt != self.latest(document["request_id"], connection)
                or attempt["attempt_number"] != command["expected_attempt_number"]
                or run["state"] != command["expected_planning_run_state"]
            ):
                raise RuntimeEventError("STATE_CONFLICT", "expected_attempt")
            scoped = TransactionEngine(self.engine, connection)
            outcome = self.orchestrator(scoped).cancel(
                PlanningRunCancelCommand(
                    planning_run_id=run["planning_run_id"],
                    expected_revision=run["revision"],
                    expected_state=run["state"],
                    expected_run_fingerprint=run["run_fingerprint"],
                    idempotency_key=key,
                    reason=command["reason"],
                ),
                context=context,
            )
            self.audits.append_in_transaction(
                connection,
                build_replan_audit_record(
                    action=ReplanAuditAction.REPLAN_ATTEMPT_LINKED,
                    aggregate_type="REPLAN_ATTEMPT",
                    aggregate_id=attempt["attempt_id"],
                    correlation_id=context.correlation_id,
                    idempotency_scope=scope,
                    idempotency_key_reference=key,
                    request_fingerprint=canonical_fingerprint(command),
                    occurred_at_utc=context.occurred_at_utc,
                ),
            )
            return outcome.aggregate.document, False

    def execute(self, request: Any) -> dict[str, Any]:
        operation = str(request.operation)
        if request.query and request.query["page"]["cursor"] is not None:
            raise RuntimeEventError("INVALID_INPUT", "query.page.cursor")
        capability = (
            "replan"
            if operation == "CREATE_REPLAN_REQUEST"
            else "replan_control"
            if operation in {"CANCEL_REPLAN_REQUEST", "RETRY_REPLAN_REQUEST"}
            else "replan_view"
        )
        binding = self.events._binding(
            request.context, request.planning_scope_id, capability
        )
        replayed = False
        if operation in {"CREATE_REPLAN_REQUEST", "RETRY_REPLAN_REQUEST"}:
            attempt, replayed = self._create(
                request, binding, retry=operation == "RETRY_REPLAN_REQUEST"
            )
            document = cast(Any, self.requests.get(attempt["request_id"]))
        else:
            query = request.query or request.document
            attempt_id = query.get("attempt_id", query.get("expected_attempt_id"))
            attempt = (
                self.latest(request.resource_id)
                if operation == "GET_REPLAN_REQUEST"
                else cast(Any, self.lineage.get_attempt(attempt_id))
            )
            if attempt is None:
                raise RuntimeEventError("SOURCE_NOT_FOUND", "attempt")
            document = cast(Any, self.requests.get(attempt["request_id"]))
            if (
                document is None
                or document["planning_scope_id"] != binding["planning_scope_id"]
                or document["factory_id"] != binding["factory_id"]
                or document["request_fingerprint"] != query["request_fingerprint"]
                or (
                    operation != "GET_CHANGE_REPORT"
                    and document["request_id"] != request.resource_id
                )
            ):
                raise RuntimeEventError("MIXED_LINEAGE", "request")
        model = self.runs.get(attempt["planning_run_id"])
        if model is None:
            raise RuntimeEventError("SOURCE_NOT_FOUND", "planning_run")
        run = model.aggregate.document
        if run["effective_scope"]["tenant_id"] != binding["tenant_id"]:
            raise RuntimeEventError("AUTHORIZATION_DENIED", "tenant")
        if operation == "CANCEL_REPLAN_REQUEST":
            run, replayed = self._cancel(request, binding, attempt, document)
        state = run["state"]
        boundary = {
            "query_fingerprint": (request.query or request.document).get(
                "query_fingerprint", canonical_fingerprint(request.document)
            ),
            "data_plane": "SIMULATION",
            "environment": request.context.environment,
            "synthetic": True,
            "production_binding": False,
        }
        actions = []
        if "replan_control" in request.context.resolved_capabilities:
            if state not in PLANNING_RUN_TERMINAL_STATES:
                actions = ["CANCEL"]
            elif state != "COMPLETED":
                actions = ["RETRY"]
        projected_attempt = {
            "attempt_id": attempt["attempt_id"],
            "attempt_number": attempt["attempt_number"],
            "planning_run_id": run["planning_run_id"],
            "state": state,
            "allowed_actions": actions,
            "updated_at_utc": run["updated_at_utc"],
        }
        result = {
            **boundary,
            "result_version": "replan-request-workspace.v1",
            "request": document,
            "attempt": projected_attempt,
        }
        if operation in {"GET_REPLAN_RESULT", "GET_CHANGE_REPORT"}:
            applied = (
                cast(
                    Any,
                    self.lineage.get_applied_result_for_attempt(attempt["attempt_id"]),
                )
                if state == "COMPLETED"
                else None
            )
            if operation == "GET_CHANGE_REPORT":
                if (
                    applied is None
                    or state != "COMPLETED"
                    or applied.change_report["report_id"] != request.resource_id
                    or applied.change_report["report_fingerprint"]
                    != request.query["report_fingerprint"]
                ):
                    raise RuntimeEventError("MIXED_LINEAGE", "change_report")
                before = applied.change_report["before_kpi"]
                after = applied.change_report["after_kpi"]
                frozen = model.aggregate.prepared_artifacts["runtime_replan"]
                before_seconds = frozen["before_kpi"]["delivery"][
                    "priority_weighted_tardiness_seconds"
                ]
                after_seconds = applied.kpi["delivery"][
                    "priority_weighted_tardiness_seconds"
                ]
                result = {
                    **boundary,
                    "result_version": "change-report-workspace.v1",
                    "report": applied.change_report,
                    "read_model_version": "change-report-read-model.v1",
                    "next_cursor": None,
                    "publishable": False,
                    "tardiness": {
                        "metric": "priority_weighted_tardiness_seconds",
                        "before_seconds": before_seconds,
                        "after_seconds": after_seconds,
                        "delta_seconds": after_seconds - before_seconds,
                        "before_kpi": before,
                        "after_kpi": after,
                    },
                }
            else:
                result = {
                    **boundary,
                    "result_version": "replan-result-workspace.v1",
                    "request_id": document["request_id"],
                    "request_fingerprint": document["request_fingerprint"],
                    **{
                        k: projected_attempt[k]
                        for k in ("attempt_id", "attempt_number", "planning_run_id")
                    },
                    "planning_run_state": state,
                    "new_schedule_version": None,
                    "change_report": None,
                    "failure_reason": None
                    if state not in PLANNING_RUN_TERMINAL_STATES or state == "COMPLETED"
                    else state,
                    "correlation_id": request.context.correlation_id,
                }
                if applied is not None and state == "COMPLETED":
                    report = applied.change_report
                    result["new_schedule_version"] = report["new_schedule_version"]
                    result["change_report"] = {
                        k: report[k]
                        for k in (
                            "change_report_version",
                            "report_id",
                            "report_fingerprint",
                        )
                    }
        result["projection_fingerprint"] = canonical_fingerprint(result)
        return {
            "response_version": "dynamic-replanning-response.v1",
            "operation": operation,
            "resource_type": "CHANGE_REPORT"
            if operation == "GET_CHANGE_REPORT"
            else "REPLAN_RESULT"
            if operation == "GET_REPLAN_RESULT"
            else "REPLAN_REQUEST",
            "resource_id": request.resource_id,
            "result": result,
            "replayed": replayed,
            "correlation_id": request.context.correlation_id,
        }
