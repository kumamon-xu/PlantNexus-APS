import { sha256Fingerprint } from "../src/api/canonical";
import type { JsonObject } from "../src/api/types";
import {
  parseChangeReportResponse,
  parseRequestResponse,
  parseResultResponse,
  parseTimelineResponse,
} from "../src/features/replanning/contracts";
import {
  buildChangeReportQuery,
  buildRequestQuery,
  buildResultQuery,
  buildTimelineQuery,
} from "../src/features/replanning/query";
import {
  p4Fingerprint,
  p4Identity,
  p4ReportId,
  p4Runtime,
  responseForQuery,
} from "./replanningFixtures";

describe("TEST-REPLAN-FRONTEND-001 strict P4 consumer contracts", () => {
  it("binds the four server projections without client KPI or ordering calculations", async () => {
    const [timelineQuery, requestQuery, resultQuery, reportQuery] = await Promise.all([
      buildTimelineQuery(p4Runtime, p4Identity),
      buildRequestQuery(p4Runtime, p4Identity),
      buildResultQuery(p4Runtime, p4Identity),
      buildChangeReportQuery(
        p4Runtime,
        p4Identity,
        p4ReportId,
        p4Fingerprint("7"),
      ),
    ]);
    const timeline = await parseTimelineResponse(
      await responseForQuery(timelineQuery),
      timelineQuery,
    );
    const request = await parseRequestResponse(
      await responseForQuery(requestQuery),
      requestQuery,
    );
    const result = await parseResultResponse(
      await responseForQuery(resultQuery),
      resultQuery,
    );
    const report = await parseChangeReportResponse(
      await responseForQuery(reportQuery),
      reportQuery,
    );

    expect(timeline.events.map((item) => item.source_position)).toEqual([1, 2]);
    expect(request.request.freeze_resolution).toMatchObject({
      window_seconds: 900,
      effective_lock_ids: ["lock-p4-ui-freeze-001"],
    });
    expect(result).toMatchObject({ planning_run_state: "COMPLETED" });
    expect(report.tardiness).toMatchObject({
      before_seconds: 600,
      after_seconds: 300,
      delta_seconds: -300,
    });
    expect(report.report.stability.absolute_start_shift_seconds).toBe(300);
  });

  it("fails closed on projection tamper, unknown state and reordered event source positions", async () => {
    const timelineQuery = await buildTimelineQuery(p4Runtime, p4Identity);
    const requestQuery = await buildRequestQuery(p4Runtime, p4Identity);
    const tampered = await responseForQuery(timelineQuery);
    tampered.result.through_position = 99;
    await expect(parseTimelineResponse(tampered, timelineQuery)).rejects.toThrow(
      "timeline authority differs",
    );

    const unknown = await responseForQuery(requestQuery);
    (unknown.result.attempt as JsonObject).state = "FUTURE_STATE";
    await expect(parseRequestResponse(unknown, requestQuery)).rejects.toThrow(
      "unknown PlanningRun state",
    );

    const reordered = await responseForQuery(timelineQuery);
    const events = reordered.result.events as JsonObject[];
    reordered.result.events = [events[1]!, events[0]!];
    reordered.result.projection_fingerprint = await sha256Fingerprint(
      Object.fromEntries(
        Object.entries(reordered.result).filter(([key]) => key !== "projection_fingerprint"),
      ) as JsonObject,
    );
    await expect(parseTimelineResponse(reordered, timelineQuery)).rejects.toThrow(
      "server order is not contiguous",
    );
  });
});
