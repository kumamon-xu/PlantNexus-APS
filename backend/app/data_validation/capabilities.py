"""Capability declaration and resource-option eligibility validation."""

from __future__ import annotations

from collections.abc import Mapping

from app.domain.capabilities import CAPABILITY_STATUS_BY_NAME, CapabilityStatus
from app.domain.errors import ProductErrorCodeV2

from .contracts import IssueCollector
from .references import CanonicalView, add_record_issue


_PLATFORM_STATUS_BY_NAME = {
    name.value: status for name, status in CAPABILITY_STATUS_BY_NAME.items()
}


def validate_capabilities_and_resources(
    view: CanonicalView, issues: IssueCollector
) -> None:
    """Reject unsupported declarations and operations with no eligible resource."""

    resource_capabilities = _validate_resource_capabilities(view, issues)
    options_by_operation: dict[str, list[Mapping[str, object]]] = {}
    for option in view.records("routing_resource_options"):
        operation_id = option.get("routing_operation_id")
        if isinstance(operation_id, str):
            options_by_operation.setdefault(operation_id, []).append(option)

    option_resources_by_operation: dict[str, set[str]] = {}
    for operation in view.records("routing_operations"):
        operation_id = operation.get("routing_operation_id")
        if not isinstance(operation_id, str):
            continue
        required, blocked = _validate_required_capabilities(
            view, issues, operation
        )
        options = sorted(
            options_by_operation.get(operation_id, []),
            key=lambda option: str(option.get("routing_resource_option_id", "")),
        )
        if not options:
            add_record_issue(
                issues,
                view,
                "routing_operations",
                operation,
                ProductErrorCodeV2.MISSING_RESOURCE,
                field="routing_resource_options",
                observed_value=[],
                expected_contract="at least one explicit resource option per routing operation",
                action="provide an authoritative resource option with duration provenance",
                message="Routing operation has no resource options",
            )
            option_resources_by_operation[operation_id] = set()
            continue
        referenced_resources = {
            resource_id
            for option in options
            if isinstance((resource_id := option.get("resource_id")), str)
        }
        option_resources_by_operation[operation_id] = referenced_resources
        if blocked:
            continue
        eligible: list[str] = []
        observed: list[dict[str, object]] = []
        for option in options:
            resource_id = option.get("resource_id")
            capabilities = (
                resource_capabilities.get(resource_id)
                if isinstance(resource_id, str)
                else None
            )
            if capabilities is None:
                observed.append(
                    {
                        "resource_id": resource_id,
                        "missing_capabilities": sorted(required),
                        "resolvable": False,
                    }
                )
                continue
            missing = sorted(required - capabilities)
            observed.append(
                {
                    "resource_id": resource_id,
                    "missing_capabilities": missing,
                    "resolvable": True,
                }
            )
            if not missing:
                eligible.append(str(resource_id))
        if not eligible:
            add_record_issue(
                issues,
                view,
                "routing_operations",
                operation,
                ProductErrorCodeV2.MISSING_RESOURCE,
                field="required_capabilities/resource_options",
                observed_value=observed,
                expected_contract="at least one resolvable resource option satisfies all operational capabilities",
                action="add a capability-eligible resource option or repair resource capabilities",
                message="Routing operation has no capability-eligible resource",
            )

    _validate_fact_and_lock_option_membership(
        view, issues, option_resources_by_operation
    )


def _validate_resource_capabilities(
    view: CanonicalView, issues: IssueCollector
) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for resource in view.records("resources"):
        resource_id = resource.get("resource_id")
        raw = resource.get("capabilities")
        parsed = _validate_capability_list(
            view,
            issues,
            "resources",
            resource,
            raw,
            allow_empty=False,
        )
        if isinstance(resource_id, str) and view.get("resources", resource_id) is resource:
            result[resource_id] = parsed
    return result


def _validate_required_capabilities(
    view: CanonicalView,
    issues: IssueCollector,
    operation: Mapping[str, object],
) -> tuple[set[str], bool]:
    declared = _validate_capability_list(
        view,
        issues,
        "routing_operations",
        operation,
        operation.get("required_capabilities"),
        allow_empty=False,
    )
    blocked = False
    operational: set[str] = set()
    for capability in sorted(declared):
        status = _PLATFORM_STATUS_BY_NAME.get(capability)
        if status is None:
            operational.add(capability)
        elif status is not CapabilityStatus.V1_SUPPORTED:
            blocked = True
            add_record_issue(
                issues,
                view,
                "routing_operations",
                operation,
                ProductErrorCodeV2.UNSUPPORTED_CAPABILITY,
                field="required_capabilities",
                observed_value={"capability": capability, "status": status.value},
                expected_contract="only V1_SUPPORTED platform capability declarations",
                action="remove the declaration or deliver its separately gated capability",
                message="Routing operation declares an unsupported platform capability",
            )
    return operational, blocked


def _validate_capability_list(
    view: CanonicalView,
    issues: IssueCollector,
    collection: str,
    record: Mapping[str, object],
    raw: object,
    *,
    allow_empty: bool,
) -> set[str]:
    if not isinstance(raw, list) or (not raw and not allow_empty):
        if raw is not None:
            add_record_issue(
                issues,
                view,
                collection,
                record,
                ProductErrorCodeV2.INVALID_CAPABILITY_DECLARATION,
                field=(
                    "capabilities"
                    if collection == "resources"
                    else "required_capabilities"
                ),
                observed_value=raw,
                expected_contract="non-empty array of explicit capability names",
                action="provide valid explicit capability declarations",
                message="Capability declaration list is invalid",
            )
        return set()
    parsed: list[str] = []
    invalid: list[object] = []
    for value in raw:
        if not isinstance(value, str) or not value.strip():
            invalid.append(value)
        else:
            parsed.append(value)
    field = "capabilities" if collection == "resources" else "required_capabilities"
    if invalid:
        add_record_issue(
            issues,
            view,
            collection,
            record,
            ProductErrorCodeV2.INVALID_CAPABILITY_DECLARATION,
            field=field,
            observed_value=invalid,
            expected_contract="non-empty capability-name strings",
            action="remove or repair malformed capability values",
            message="Capability declaration contains invalid names",
        )
    duplicates = sorted({value for value in parsed if parsed.count(value) > 1})
    if duplicates:
        add_record_issue(
            issues,
            view,
            collection,
            record,
            ProductErrorCodeV2.DUPLICATE_CAPABILITY,
            field=field,
            observed_value=duplicates,
            expected_contract="unique capability declarations within one record",
            action="deduplicate the capability list",
            message="Capability declaration contains duplicates",
        )
    return set(parsed)


def _validate_fact_and_lock_option_membership(
    view: CanonicalView,
    issues: IssueCollector,
    option_resources_by_operation: Mapping[str, set[str]],
) -> None:
    for collection in ("execution_facts", "operation_locks"):
        for record in view.records(collection):
            operation_id = record.get("routing_operation_id")
            resource_id = record.get("resource_id")
            if not isinstance(operation_id, str) or not isinstance(resource_id, str):
                continue
            if view.get("resources", resource_id) is None:
                continue
            if resource_id not in option_resources_by_operation.get(operation_id, set()):
                add_record_issue(
                    issues,
                    view,
                    collection,
                    record,
                    ProductErrorCodeV2.MISSING_RESOURCE,
                    field="resource_id",
                    observed_value=resource_id,
                    expected_contract="resource is an explicit option for the routing operation",
                    action="repair the fact/lock resource or the authoritative routing option",
                    message="Fact or lock resource is not eligible for its routing operation",
                )


__all__ = ["validate_capabilities_and_resources"]
