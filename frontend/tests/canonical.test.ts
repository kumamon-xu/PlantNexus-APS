import { canonicalJson, sha256Fingerprint, workspaceQueryFingerprint } from "../src/api/canonical";
import { buildWorkspaceQuery } from "../src/api/query";

describe("canonical-json.v1", () => {
  it("sorts mapping keys and preserves compact UTF-8 JSON", async () => {
    const value = { z: "排程", a: { second: 2, first: 1 } };
    expect(canonicalJson(value)).toBe('{"a":{"first":1,"second":2},"z":"排程"}');
    expect(await sha256Fingerprint(value)).toMatch(/^sha256:[0-9a-f]{64}$/);
  });

  it("matches the frozen Python workspace-query sample vector", async () => {
    const query = {
      workspace_query_version: "workspace-query.v1",
      schema_set_version: "2.6.0",
      canonicalization_version: "canonical-json.v1",
      direction: "RESULT",
      query_kind: "WORKSPACE_VIEW",
      data_plane: "SIMULATION",
      environment: "TEST",
      synthetic: true,
      synthetic_provenance: {
        scenario_id: "SIM-P2-GOLDEN-JSSP-001",
        scenario_version: "1.0.0",
        seed: 20260824,
        factory_profile_id: "PROFILE-P2-XS-001",
        profile_version: "1.0.0",
        generator_id: "PLANTNEXUS-P2-CORRECTNESS-ASSEMBLER",
        generator_version: "1.0.0",
      },
      resource: { resource_type: "SCHEDULE_VERSION", resource_id: "schedule-version-sim-001" },
      view: "GANTT",
      schedule_version_precondition: {
        schedule_version_id: "schedule-version-sim-001",
        state: "DRAFT",
        content_fingerprint: `sha256:${"a04434045794169cf0556ce7c43cf4969aaabfb5a77e4f19e4f8ccd9bbd6e4ac"}`,
      },
      sort: [
        { field: "START_AT_UTC", direction: "ASC" },
        { field: "ITEM_ID", direction: "ASC" },
      ],
      filters: {
        order_ids: [],
        operation_ids: [],
        resource_ids: [],
        states: ["DRAFT"],
        start_at_or_after_utc: "2026-08-24T00:00:00Z",
        start_before_utc: "2026-08-25T00:00:00Z",
      },
      page: { size: 100, cursor: null },
      query_fingerprint: `sha256:${"0".repeat(64)}`,
      correlation_id: "ignored-by-projection",
      result: null,
    };
    expect(await workspaceQueryFingerprint(query)).toBe(
      "sha256:f787014a4922c2a3e1f11ace427a265b885d0154c18b616b150d4d13ebcd5a83",
    );
  });

  it("builds an exact request fingerprint without a floating default", async () => {
    const query = await buildWorkspaceQuery({
      authority: { dataPlane: "PRODUCTION", environment: "PRODUCTION", synthetic: false },
      view: "DATA_HEALTH",
      correlationId: "correlation-test-query-builder",
    });
    expect(query.query_fingerprint).toBe(await workspaceQueryFingerprint(query));
    expect(query.direction).toBe("REQUEST");
    expect(query.result).toBeNull();
  });
});
