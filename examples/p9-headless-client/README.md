# P9 Runtime HTTP consumer

This standard-library Python example uses the same `/api/v1` operations as the optional Planning Workspace. It imports no APS backend, ORM, Solver, queue or Frontend package. Supply a configured TEST/SIMULATION Runtime and an approved short-lived session; credentials remain in memory.

```python
from getpass import getpass
import json
from runtime_client import RuntimeClient

client = RuntimeClient("http://127.0.0.1:8000", getpass("Runtime session: "))
with open("approved-event.json", encoding="utf-8") as stream:
    event = json.load(stream)
receipt = client.submit(event, "host-event-key-000001")
```

Event acceptance only appends the ledger. The trusted Runtime operator must explicitly call the existing fact-projection Python port and prepare a complete, approved `replan-request.v1` from that checkpoint, Problem, Policy and freeze resolution. There is no public preparation endpoint. The browser and this client do not manufacture those facts. After that handoff:

```python
with open("approved-replan.json", encoding="utf-8") as stream:
    request = json.load(stream)
queued = client.submit(request, "host-replan-key-000001")
attempt = queued["result"]["attempt"]
# Persist request/attempt identities and the original key in host-owned storage.
# Poll with the approved dynamic-replanning-query.v1 carrier:
result = client.request("GET", f"/api/v1/replan-requests/{request['request_id']}/result",
                        query=approved_result_query)
```

Use `client.command(approved_workspace_command)` for manual changes, validation submission, approval and internal publication. Every command includes the exact source state/content fingerprint, a reason and a stable idempotency key. Manual changes return a new `new_version`; re-read it with `client.version(id)`. Publication must explicitly identify the previous current PUBLISHED version, or `null` for the first publication. A queued or completed solve never implies approval or publication.

| Consumer input/output | Supported behavior |
|---|---|
| `schedule-version.v1` | Raw detail; server-authorized manual edit/lock, review, decision and publication |
| `schedule-version.v2` | Preserve replan lineage; review, decision and publication; content edits explicitly rejected |
| Old workspace views / comparison / export | Consume only compatible sources; changed manual content or v2 must not be relabeled as old Solution/KPI |
| `execution-event.v1` | Append/replay; query authoritative ledger; projection remains an explicit server step |
| `replan-request.v1` | Create/query; explicit cancel/retry of the current attempt; result and ChangeReport are server facts |
| Unknown version, stale state, unauthorized, invalid source | Visible failure; no successful local state or automatic replacement key |

`RuntimeFailure.status` preserves HTTP status; network POST failures are `UNKNOWN_OUTCOME`. Reconcile the original resource/attempt before retrying; never infer rollback from a lost response. The example does not implement production SSO or business mapping.

The real TCP tests are `backend/tests/integration/test_p9_consumers.py`. The installed-wheel replay verifies that the Runtime and SDK load outside the source checkout without Frontend dependencies. The dedicated Chromium test receives approved fixture documents through the test runner's filesystem; all browser business requests go through the same formal HTTP API, without mocked routes or test-only HTTP endpoints.
