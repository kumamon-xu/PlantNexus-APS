"""Verify D17 raw benchmark evidence and seal the versioned baseline."""

from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any, NoReturn, cast


DEMO_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = DEMO_ROOT.parent
TASK_ID = "TASK-DEMO-09"
EVIDENCE_VERSION = "cnc-demo-benchmark-evidence.v1"
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))
sys.path.insert(0, str(DEMO_ROOT / "backend"))

from plantnexus_demo.formal_benchmark import (  # noqa: E402
    FORMAL_SAMPLE_VERSION,
    FORMAL_SUITE_VERSION,
    PROFILE_NAMES,
    distribution,
    fingerprint,
    load_formal_protocol,
    showcase_thresholds,
    summarize_profile,
)


class EvidenceFailure(RuntimeError):
    """Stable evidence verification failure."""


def _fail(code: str) -> NoReturn:
    raise EvidenceFailure(code)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EvidenceFailure("JSON_READ_FAILED") from error
    if not isinstance(value, dict):
        _fail("JSON_NOT_OBJECT")
    return cast(dict[str, Any], value)


def _verify_fingerprint(document: Mapping[str, Any], field: str) -> str:
    expected = document.get(field)
    if not isinstance(expected, str):
        _fail(f"{field.upper()}_MISSING")
    payload = {key: value for key, value in document.items() if key != field}
    if fingerprint(payload) != expected:
        _fail(f"{field.upper()}_MISMATCH")
    return expected


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _repository_relative(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError as error:
        raise EvidenceFailure("EVIDENCE_PATH_OUTSIDE_REPOSITORY") from error


def _resolve_below(parent: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative:
        _fail("INVALID_RELATIVE_PATH")
    candidate = (parent / relative).resolve()
    if parent.resolve() not in candidate.parents:
        _fail("RELATIVE_PATH_ESCAPE")
    return candidate


def _verify_source_digests(document: Mapping[str, Any]) -> int:
    sources = document.get("source_sha256")
    if not isinstance(sources, Mapping) or not sources:
        _fail("SOURCE_DIGESTS_MISSING")
    for relative, expected in sources.items():
        if not isinstance(relative, str) or not isinstance(expected, str):
            _fail("INVALID_SOURCE_DIGEST")
        path = (REPOSITORY_ROOT / relative).resolve()
        if REPOSITORY_ROOT not in path.parents or not path.is_file():
            _fail("SOURCE_PATH_INVALID")
        if _file_sha256(path) != expected:
            _fail("SOURCE_DIGEST_MISMATCH")
    return len(sources)


def _numeric(sample: Mapping[str, Any], key: str) -> float:
    value = sample.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        _fail(f"INVALID_BROWSER_METRIC_{key.upper()}")
    return float(value)


def _dom_numeric(sample: Mapping[str, Any], key: str) -> float:
    dom = sample.get("dom")
    if not isinstance(dom, Mapping):
        _fail("INVALID_BROWSER_DOM")
    return _numeric(cast(Mapping[str, Any], dom), key)


def _browser_summary(
    state: str,
    samples: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    measured = [
        sample
        for sample in samples
        if sample.get("state") == state and sample.get("role") == "measured"
    ]
    if len(measured) != 5:
        _fail("BROWSER_MEASURED_SAMPLE_COUNT_MISMATCH")
    return {
        "status": "PASS",
        "measured_sample_count": 5,
        "warmup_excluded": True,
        "percentile_method": "nearest-rank",
        "distributions": {
            "ready_milliseconds": distribution(
                [_numeric(sample, "ready_milliseconds") for sample in measured]
            ),
            "navigation_dom_content_loaded_milliseconds": distribution(
                [
                    _numeric(sample, "navigation_dom_content_loaded_milliseconds")
                    for sample in measured
                ]
            ),
            "navigation_load_event_milliseconds": distribution(
                [
                    _numeric(sample, "navigation_load_event_milliseconds")
                    for sample in measured
                ]
            ),
            "api_max_milliseconds": distribution(
                [_numeric(sample, "api_max_milliseconds") for sample in measured]
            ),
            "api_response_count": distribution(
                [_numeric(sample, "api_response_count") for sample in measured]
            ),
            "api_encoded_body_bytes_total": distribution(
                [
                    _numeric(sample, "api_encoded_body_bytes_total")
                    for sample in measured
                ]
            ),
            "dom_element_count": distribution(
                [_dom_numeric(sample, "element_count") for sample in measured]
            ),
            "document_html_bytes": distribution(
                [_dom_numeric(sample, "document_html_bytes") for sample in measured]
            ),
        },
    }


def verify_backend(path: Path) -> dict[str, Any]:
    suite = _read_json(path)
    suite_fingerprint = _verify_fingerprint(suite, "suite_fingerprint")
    if (
        suite.get("suite_version") != FORMAL_SUITE_VERSION
        or suite.get("task_id") != TASK_ID
        or suite.get("status") != "PASS"
    ):
        _fail("BACKEND_SUITE_NOT_PASS")
    protocol = load_formal_protocol(DEMO_ROOT)
    protocol_ref = suite.get("protocol")
    if not isinstance(protocol_ref, Mapping) or (
        protocol_ref.get("fingerprint") != protocol.fingerprint
        or protocol_ref.get("baseline_version") != protocol.baseline_version
    ):
        _fail("BACKEND_PROTOCOL_MISMATCH")

    environment_ref = suite.get("environment")
    if not isinstance(environment_ref, Mapping):
        _fail("BACKEND_ENVIRONMENT_REFERENCE_MISSING")
    environment_path = _resolve_below(path.parent, environment_ref.get("path"))
    environment = _read_json(environment_path)
    environment_fingerprint = _verify_fingerprint(
        environment, "environment_fingerprint"
    )
    if environment_ref.get("fingerprint") != environment_fingerprint:
        _fail("BACKEND_ENVIRONMENT_FINGERPRINT_MISMATCH")
    backend_source_count = _verify_source_digests(environment)

    inventory = suite.get("sample_inventory")
    if not isinstance(inventory, list) or len(inventory) != 21:
        _fail("BACKEND_SAMPLE_INVENTORY_MISMATCH")
    samples_by_profile: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    identities: set[tuple[str, str, int]] = set()
    for raw_item in inventory:
        if not isinstance(raw_item, Mapping):
            _fail("BACKEND_SAMPLE_INVENTORY_INVALID")
        item = cast(Mapping[str, Any], raw_item)
        profile = item.get("profile")
        role = item.get("role")
        sequence = item.get("sequence")
        if (
            profile not in PROFILE_NAMES
            or role not in {"preflight", "warmup", "measured"}
            or not isinstance(sequence, int)
            or isinstance(sequence, bool)
        ):
            _fail("BACKEND_SAMPLE_IDENTITY_INVALID")
        identity = (cast(str, profile), cast(str, role), sequence)
        if identity in identities:
            _fail("BACKEND_SAMPLE_IDENTITY_DUPLICATE")
        identities.add(identity)
        sample_path = _resolve_below(path.parent, item.get("path"))
        sample = _read_json(sample_path)
        sample_fingerprint = _verify_fingerprint(sample, "sample_fingerprint")
        if (
            sample.get("sample_version") != FORMAL_SAMPLE_VERSION
            or sample.get("sample_id")
            != f"{profile}-{role}-{sequence:02d}"
            or sample.get("status") != "PASS"
            or item.get("status") != "PASS"
            or item.get("sample_fingerprint") != sample_fingerprint
        ):
            _fail("BACKEND_SAMPLE_NOT_PASS")
        samples_by_profile[cast(str, profile)].append(sample)

    summaries = suite.get("profiles")
    if not isinstance(summaries, Mapping) or set(summaries) != set(PROFILE_NAMES):
        _fail("BACKEND_PROFILE_SUMMARIES_MISSING")
    recomputed: dict[str, Any] = {}
    for profile in PROFILE_NAMES:
        summary = summarize_profile(profile, samples_by_profile[profile])
        if summary != summaries[profile] or summary.get("status") != "PASS":
            _fail("BACKEND_PROFILE_SUMMARY_MISMATCH")
        recomputed[profile] = summary
    threshold_result = showcase_thresholds(recomputed["showcase"], protocol)
    if (
        threshold_result != suite.get("showcase_thresholds")
        or threshold_result.get("status") != "PASS"
    ):
        _fail("SHOWCASE_THRESHOLD_MISMATCH")
    upper = suite.get("upper_characterization")
    freeze = suite.get("parameter_freeze")
    if (
        not isinstance(upper, Mapping)
        or upper.get("status") != "PASS"
        or not isinstance(freeze, Mapping)
        or freeze.get("status") != "FROZEN"
        or freeze.get("protocol_fingerprint") != protocol.fingerprint
        or freeze.get("urgent_fixture") != protocol.urgent_fixture
    ):
        _fail("PARAMETER_FREEZE_NOT_ESTABLISHED")
    return {
        "document": suite,
        "fingerprint": suite_fingerprint,
        "environment": environment,
        "environment_path": environment_path,
        "environment_fingerprint": environment_fingerprint,
        "source_count": backend_source_count,
        "sample_count": len(inventory),
        "profiles": recomputed,
        "thresholds": threshold_result,
    }


def verify_browser(path: Path) -> dict[str, Any]:
    observation = _read_json(path)
    report_fingerprint = _verify_fingerprint(observation, "report_fingerprint")
    protocol = load_formal_protocol(DEMO_ROOT)
    protocol_ref = observation.get("protocol")
    if (
        observation.get("observation_version")
        != "cnc-demo-browser-benchmark-observation.v1"
        or observation.get("task_id") != TASK_ID
        or observation.get("status") != "PASS"
        or not isinstance(protocol_ref, Mapping)
        or protocol_ref.get("fingerprint") != protocol.fingerprint
        or observation.get("fixed_urgent_fixture") != protocol.urgent_fixture
    ):
        _fail("BROWSER_OBSERVATION_NOT_PASS")
    source_count = _verify_source_digests(observation)
    raw_samples = observation.get("samples")
    if not isinstance(raw_samples, list) or len(raw_samples) != 12:
        _fail("BROWSER_SAMPLE_COUNT_MISMATCH")
    samples: list[Mapping[str, Any]] = []
    for raw_sample in raw_samples:
        if not isinstance(raw_sample, Mapping):
            _fail("BROWSER_SAMPLE_INVALID")
        sample = cast(Mapping[str, Any], raw_sample)
        _verify_fingerprint(sample, "sample_fingerprint")
        if sample.get("status") != "PASS":
            _fail("BROWSER_SAMPLE_NOT_PASS")
        responses = sample.get("responses")
        if not isinstance(responses, list) or not responses:
            _fail("BROWSER_RESPONSE_EVIDENCE_MISSING")
        if any(
            not isinstance(response, Mapping)
            or not isinstance(response.get("status"), int)
            or cast(int, response["status"]) >= 400
            for response in responses
        ):
            _fail("BROWSER_RESPONSE_FAILED")
        samples.append(sample)
    summaries = observation.get("summaries")
    if not isinstance(summaries, Mapping):
        _fail("BROWSER_SUMMARIES_MISSING")
    recomputed = {
        state: _browser_summary(state, samples)
        for state in ("BASELINE_PUBLISHED", "DRAFT_COMPARISON_READY")
    }
    if recomputed != summaries:
        _fail("BROWSER_SUMMARY_MISMATCH")
    lifecycle = observation.get("lifecycle")
    if not isinstance(lifecycle, Mapping):
        _fail("BROWSER_LIFECYCLE_MISSING")
    changes = lifecycle.get("change_counts")
    if (
        lifecycle.get("validation_status") != "PASS"
        or lifecycle.get("current_publication_unchanged") is not True
        or not isinstance(changes, Mapping)
        or changes.get("added") != 5
        or not isinstance(changes.get("changed"), int)
        or cast(int, changes["changed"]) <= 0
        or not isinstance(changes.get("unchanged"), int)
        or cast(int, changes["unchanged"]) <= 0
    ):
        _fail("BROWSER_LIFECYCLE_NOT_PASS")
    return {
        "document": observation,
        "fingerprint": report_fingerprint,
        "source_count": source_count,
        "sample_count": len(samples),
        "summaries": recomputed,
    }


def build_baseline(
    backend_path: Path,
    browser_path: Path,
    backend: Mapping[str, Any],
    browser: Mapping[str, Any],
) -> dict[str, Any]:
    protocol = load_formal_protocol(DEMO_ROOT)
    suite = cast(Mapping[str, Any], backend["document"])
    environment = cast(Mapping[str, Any], backend["environment"])
    observation = cast(Mapping[str, Any], browser["document"])
    baseline: dict[str, Any] = {
        "baseline_version": protocol.baseline_version,
        "task_id": TASK_ID,
        "generated_at_utc": _utc_now(),
        "status": "PASS",
        "protocol": {
            "version": protocol.document["protocol_version"],
            "fingerprint": protocol.fingerprint,
            "profile_set_version": protocol.document["profile_set_version"],
        },
        "environment": {
            "role": environment["environment_role"],
            "target_machine_confirmation": environment["target_machine_confirmation"],
            "fingerprint": backend["environment_fingerprint"],
            "path": _repository_relative(cast(Path, backend["environment_path"])),
        },
        "backend": {
            "suite_path": _repository_relative(backend_path),
            "suite_sha256": _file_sha256(backend_path),
            "suite_fingerprint": backend["fingerprint"],
            "raw_sample_count": backend["sample_count"],
            "profile_summaries": backend["profiles"],
            "showcase_thresholds": backend["thresholds"],
            "upper_characterization": suite["upper_characterization"],
        },
        "browser": {
            "observation_path": _repository_relative(browser_path),
            "observation_sha256": _file_sha256(browser_path),
            "observation_fingerprint": browser["fingerprint"],
            "raw_sample_count": browser["sample_count"],
            "summaries": browser["summaries"],
            "lifecycle": observation["lifecycle"],
            "browser": observation["browser"],
        },
        "parameter_freeze": suite["parameter_freeze"],
        "verification": {
            "backend_source_digest_count": backend["source_count"],
            "browser_source_digest_count": browser["source_count"],
            "raw_samples_refingerprinted": 33,
            "summaries_recomputed_from_measured_samples": True,
            "preflight_and_warmup_excluded_from_percentiles": True,
            "percentile_method": "nearest-rank",
        },
        "boundaries": {
            "data_plane": "SIMULATION_ONLY",
            "synthetic_only": True,
            "current_environment_only": True,
            "target_machine_replay": "PENDING_D18_SITE_REPLAY",
            "production_capacity_claim": "NOT_ESTABLISHED",
            "production_sla_claim": "NOT_ESTABLISHED",
            "first_feasible_metric": "NOT_REPORTED_NO_RELIABLE_CALLBACK",
            "browser_first_screen_has_numeric_gate": False,
            "p7_registration": None,
        },
    }
    baseline["baseline_fingerprint"] = fingerprint(baseline)
    return baseline


def build_evidence(
    *,
    backend_path: Path,
    browser_path: Path,
    baseline_path: Path,
    baseline: Mapping[str, Any],
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "evidence_version": EVIDENCE_VERSION,
        "task_id": TASK_ID,
        "generated_at_utc": _utc_now(),
        "status": "PASS",
        "baseline": {
            "path": _repository_relative(baseline_path),
            "fingerprint": baseline["baseline_fingerprint"],
        },
        "inputs": {
            "backend_suite": {
                "path": _repository_relative(backend_path),
                "sha256": _file_sha256(backend_path),
            },
            "browser_observation": {
                "path": _repository_relative(browser_path),
                "sha256": _file_sha256(browser_path),
            },
        },
        "checks": {
            "protocol_and_profile_set_pinned": True,
            "backend_raw_samples_21_of_21": True,
            "browser_raw_samples_12_of_12": True,
            "source_digests_match": True,
            "environment_signature_refingerprinted": True,
            "all_sample_fingerprints_match": True,
            "all_profile_summaries_recomputed": True,
            "showcase_thresholds_pass": True,
            "validator_and_change_report_5_of_5": True,
            "upper_700_operation_characterization_pass": True,
            "fixed_urgent_fixture_matches": True,
            "published_baseline_unchanged_after_replan": True,
            "parameter_set_frozen": True,
        },
        "boundaries": baseline["boundaries"],
    }
    report["report_fingerprint"] = fingerprint(report)
    return report


def _write_exclusive(path: Path, document: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        document,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
    except FileExistsError as error:
        raise EvidenceFailure("IMMUTABLE_OUTPUT_EXISTS") from error


def verify_sealed(
    *,
    backend_path: Path,
    browser_path: Path,
    baseline_path: Path,
    report_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    backend = verify_backend(backend_path)
    browser = verify_browser(browser_path)
    baseline = _read_json(baseline_path)
    baseline_fingerprint = _verify_fingerprint(baseline, "baseline_fingerprint")
    report = _read_json(report_path)
    _verify_fingerprint(report, "report_fingerprint")
    if (
        baseline.get("baseline_version")
        != "cnc-demo-formal-benchmark-baseline.v1"
        or baseline.get("status") != "PASS"
        or cast(Mapping[str, Any], baseline.get("backend", {})).get(
            "suite_fingerprint"
        )
        != backend["fingerprint"]
        or cast(Mapping[str, Any], baseline.get("browser", {})).get(
            "observation_fingerprint"
        )
        != browser["fingerprint"]
        or report.get("evidence_version") != EVIDENCE_VERSION
        or report.get("status") != "PASS"
        or cast(Mapping[str, Any], report.get("baseline", {})).get("fingerprint")
        != baseline_fingerprint
        or cast(Mapping[str, Any], report.get("inputs", {})).get(
            "backend_suite"
        )
        != {
            "path": _repository_relative(backend_path),
            "sha256": _file_sha256(backend_path),
        }
        or cast(Mapping[str, Any], report.get("inputs", {})).get(
            "browser_observation"
        )
        != {
            "path": _repository_relative(browser_path),
            "sha256": _file_sha256(browser_path),
        }
    ):
        _fail("SEALED_EVIDENCE_MISMATCH")
    return baseline, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-suite", type=Path, required=True)
    parser.add_argument("--browser-observation", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    arguments = parser.parse_args()
    backend_path = arguments.backend_suite.resolve()
    browser_path = arguments.browser_observation.resolve()
    baseline_path = arguments.baseline.resolve()
    report_path = arguments.report.resolve()
    try:
        if arguments.verify_only:
            baseline, report = verify_sealed(
                backend_path=backend_path,
                browser_path=browser_path,
                baseline_path=baseline_path,
                report_path=report_path,
            )
        else:
            backend = verify_backend(backend_path)
            browser = verify_browser(browser_path)
            baseline = build_baseline(
                backend_path, browser_path, backend, browser
            )
            _write_exclusive(baseline_path, baseline)
            report = build_evidence(
                backend_path=backend_path,
                browser_path=browser_path,
                baseline_path=baseline_path,
                baseline=baseline,
            )
            _write_exclusive(report_path, report)
    except (EvidenceFailure, OSError, ValueError, KeyError, TypeError) as error:
        reason = str(error) if isinstance(error, EvidenceFailure) else type(error).__name__
        print(json.dumps({"status": "FAIL", "reason": reason}), flush=True)
        return 1
    print(
        json.dumps(
            {
                "status": "PASS",
                "mode": "verify" if arguments.verify_only else "seal",
                "baseline": _repository_relative(baseline_path),
                "baseline_fingerprint": baseline["baseline_fingerprint"],
                "report_fingerprint": report["report_fingerprint"],
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
