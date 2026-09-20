import schedule from "../../schemas/samples/schedule-version.v2.synthetic.json";
import request from "../../schemas/samples/replan-request.v1.synthetic.json";
import type { JsonObject } from "../src/api/types";
import { parseScheduleVersion } from "../src/api/contracts";
import { createPlanningWorkspaceClient } from "../src/api/client";
import { createDynamicReplanningClient } from "../src/features/replanning/client";
import { p4Runtime } from "./replanningFixtures";

const sample = (name: string) => structuredClone(name.startsWith("schedule") ? schedule : request) as JsonObject;
const session = { getAccessToken: async () => "p9-test-token" };

describe("P9 formal Runtime consumers", () => {
  it("preserves v2 lineage and uses permission-cropped envelope actions", () => {
    const raw = sample("schedule-version.v2.synthetic.json");
    const result = parseScheduleVersion({ ...raw, schedule_version: raw, allowed_actions: ["view"] });
    expect(result.lineage).toEqual(raw.lineage);
    expect(result.allowed_actions).toEqual(["view"]);
    expect(result.lineage.snapshot).toBeUndefined();
    expect(() => parseScheduleVersion({ ...raw, schema_set_version: "2.6.0" })).toThrow();
    expect(() => parseScheduleVersion({ ...raw, schedule_version_version: "schedule-version.v9" })).toThrow();
  });
  it("rejects a different version identity and runtime environment", async () => {
    const raw = sample("schedule-version.v2.synthetic.json");
    const client = createPlanningWorkspaceClient(p4Runtime, session, async () => new Response(JSON.stringify(raw)));
    await expect(client.getScheduleVersion("wrong-version")).rejects.toThrow();
    const other = createPlanningWorkspaceClient({ ...p4Runtime, environment: "PRODUCTION" }, session, async () => new Response(JSON.stringify(raw)));
    await expect(other.getScheduleVersion(String(raw.schedule_version_id))).rejects.toThrow();
  });
  it("rejects changed submission fingerprints before transport", async () => {
    const document = sample("replan-request.v1.synthetic.json");
    const fetcher = vi.fn();
    const client = createDynamicReplanningClient(p4Runtime, session, fetcher);
    await expect(client.submitCanonical({ ...document, trigger_reason: "ALTERED" }, "p9-submit-key-001")).rejects.toThrow();
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("preserves unknown outcome and never retries a lost POST automatically", async () => {
    const document = sample("replan-request.v1.synthetic.json");
    const fetcher = vi.fn(async () => { throw new TypeError("network lost"); });
    const client = createDynamicReplanningClient(p4Runtime, session, fetcher);
    await expect(client.submitCanonical(document, "p9-submit-key-002")).rejects.toMatchObject({ outcomeUnknown: true, status: null });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
