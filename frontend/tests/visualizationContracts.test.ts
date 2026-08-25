import { sha256Fingerprint } from "../src/api/canonical";
import {
  parseGanttSegments,
  parseResourceLoads,
  parseVersionComparison,
  parseWorkspaceResponse,
} from "../src/api/contracts";
import { buildWorkspaceQuery } from "../src/api/query";
import {
  comparisonPayload,
  ganttPayload,
  resourceLoadPayload,
  testScheduleVersion,
  workspaceResponse,
} from "./fixtures";

const authority = {
  dataPlane: "PRODUCTION" as const,
  environment: "PRODUCTION" as const,
  synthetic: false as const,
};

describe("P3-12 visualization read contracts", () => {
  it("builds stable server filter/sort carriers without a command identity", async () => {
    const gantt = await buildWorkspaceQuery({
      authority,
      view: "GANTT",
      scheduleVersion: testScheduleVersion,
      filters: { order_ids: ["order-test-1"], resource_ids: ["resource-test-1"] },
    });
    expect(gantt.query_kind).toBe("WORKSPACE_VIEW");
    expect(gantt.sort).toEqual([
      { field: "START_AT_UTC", direction: "ASC" },
      { field: "ITEM_ID", direction: "ASC" },
    ]);
    expect(gantt.filters).toMatchObject({
      order_ids: ["order-test-1"],
      resource_ids: ["resource-test-1"],
    });

    const comparison = await buildWorkspaceQuery({
      authority,
      view: "VERSION_COMPARISON",
      scheduleVersion: testScheduleVersion,
      pageSize: 1,
    });
    expect(comparison.query_kind).toBe("SCHEDULE_VERSION_COMPARISON");
    expect(JSON.stringify(comparison)).not.toContain("idempotency");
  });

  it("accepts complete Gantt, Resource Load and server comparison payloads", async () => {
    const gantt = await workspaceResponse("GANTT", {
      payloads: [ganttPayload()],
      scheduleVersion: testScheduleVersion,
    });
    const load = await workspaceResponse("RESOURCE_LOAD", {
      payloads: [resourceLoadPayload],
      scheduleVersion: testScheduleVersion,
    });
    const comparison = await workspaceResponse("VERSION_COMPARISON", {
      payloads: [comparisonPayload],
      scheduleVersion: testScheduleVersion,
    });
    expect(parseGanttSegments(await parseWorkspaceResponse(gantt, "GANTT"))).toHaveLength(1);
    expect(parseResourceLoads(await parseWorkspaceResponse(load, "RESOURCE_LOAD"))[0]).toMatchObject({
      resource_id: "resource-test-1",
      utilization: 0.5,
    });
    expect(
      parseVersionComparison(
        await parseWorkspaceResponse(comparison, "VERSION_COMPARISON"),
      ).operation_deltas.map((delta) => delta.change_kind),
    ).toEqual(["START_SHIFT", "UNCHANGED"]);
  });

  it("fails visibly on an invalid timestamp without dropping a segment", async () => {
    const response = await workspaceResponse("GANTT", {
      payloads: [ganttPayload()],
      scheduleVersion: testScheduleVersion,
    });
    response.items[0]!.payload.end_at_utc = "not-utc";
    response.items[0]!.payload_fingerprint = await sha256Fingerprint(
      response.items[0]!.payload,
    );
    response.document.result!.items[0]!.payload_fingerprint =
      response.items[0]!.payload_fingerprint;
    await expect(parseWorkspaceResponse(response, "GANTT")).rejects.toThrow(
      /explicit UTC instant/u,
    );
  });

  it("rejects an unknown server comparison classification", async () => {
    const invalid = structuredClone(comparisonPayload);
    const deltas = invalid.operation_deltas;
    if (!Array.isArray(deltas) || typeof deltas[0] !== "object" || deltas[0] === null) {
      throw new Error("fixture is incomplete");
    }
    (deltas[0] as Record<string, unknown>).change_kind = "CLIENT_GUESSED";
    const response = await workspaceResponse("VERSION_COMPARISON", {
      payloads: [invalid],
      scheduleVersion: testScheduleVersion,
    });
    await expect(
      parseWorkspaceResponse(response, "VERSION_COMPARISON"),
    ).rejects.toThrow(/unsupported server change kind/u);
  });
});
