import { describe, expect, it, vi } from "vitest";

import {
  buildComparisonQuery,
  buildScheduleQuery,
  createDemoApi,
  DemoClientError,
} from "../src/api/client";
import {
  comparisonView,
  emptyBootstrap,
  factoryView,
  scheduleView,
} from "./fixtures";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json", "X-Correlation-Id": "correlation-test" },
  });
}

describe("Demo 同源 API client", () => {
  it("先建立 HttpOnly session，再以 same-origin 凭据读取状态", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        jsonResponse({
          session_version: "cnc-demo-local-session.v1",
          status: "ESTABLISHED",
          simulation_only: true,
        }),
      )
      .mockResolvedValueOnce(jsonResponse(emptyBootstrap()));
    vi.stubGlobal("fetch", fetchMock);
    const api = createDemoApi();

    await api.establishSession();
    const state = await api.bootstrap();

    expect(state.story_state).toBe("EMPTY");
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/demo/v1/session",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/demo/v1/bootstrap",
      expect.objectContaining({ credentials: "same-origin" }),
    );
  });

  it("写命令携带幂等键且不要求底层 identity", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse({
        job_accepted_version: "cnc-demo-job-accepted.v1",
        job_id: "job-reset-demo",
        job_kind: "RESET",
        run_id: null,
        status: "QUEUED",
        replayed: false,
      }, 202),
    );
    vi.stubGlobal("fetch", fetchMock);
    const api = createDemoApi();

    await api.reset("showcase", "demo-idempotency-key-1234");

    const init = fetchMock.mock.calls[0]?.[1];
    const headers = new Headers(init?.headers);
    expect(headers.get("Idempotency-Key")).toBe("demo-idempotency-key-1234");
    expect(JSON.parse(String(init?.body))).toEqual({
      request_version: "cnc-demo-reset-request.v1",
      profile_name: "showcase",
    });
  });

  it("丢弃服务端原始 message，只暴露稳定错误码", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(
        jsonResponse(
          {
            error_version: "cnc-demo-error.v1",
            code: "AUTHORIZATION_DENIED",
            field: "authorization",
            message: "Bearer highly-sensitive-value",
            correlation_id: "correlation-denied",
          },
          403,
        ),
      ),
    );
    const api = createDemoApi();

    const error = await api.bootstrap().catch((reason: unknown) => reason);

    expect(error).toBeInstanceOf(DemoClientError);
    expect(error).toMatchObject({ code: "AUTHORIZATION_DENIED" });
    expect(String(error)).not.toContain("highly-sensitive-value");
  });

  it("用排序去重的重复参数读取工厂和不超过 200 条的排程页", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(factoryView()))
      .mockResolvedValueOnce(jsonResponse(scheduleView()));
    vi.stubGlobal("fetch", fetchMock);
    const api = createDemoApi();

    await api.getFactory();
    await api.getSchedulePage("schedule-demo", {
      resource_ids: ["resource-b", "resource-a", "resource-b"],
      states: ["RUNNING", "NOT_STARTED"],
      start_at_utc: "2026-09-06T16:00:00Z",
      end_at_utc: "2026-09-09T16:00:00Z",
      sort: "RESOURCE_START_ASC",
      limit: 160,
    });

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/demo/v1/factory");
    const scheduleUrl = String(fetchMock.mock.calls[1]?.[0]);
    const parsed = new URL(scheduleUrl, "http://demo.local");
    expect(parsed.pathname).toBe("/api/demo/v1/versions/schedule-demo");
    expect(parsed.searchParams.getAll("resource_id")).toEqual([
      "resource-a",
      "resource-b",
    ]);
    expect(parsed.searchParams.getAll("state")).toEqual([
      "NOT_STARTED",
      "RUNNING",
    ]);
    expect(parsed.searchParams.get("limit")).toBe("160");
    expect(fetchMock.mock.calls[1]?.[1]).toEqual(
      expect.objectContaining({ credentials: "same-origin" }),
    );
  });

  it("在发请求前拒绝超出工作区上限或倒置的时间窗", () => {
    expect(() => buildScheduleQuery({ limit: 201 })).toThrow();
    expect(() =>
      buildScheduleQuery({
        start_at_utc: "2026-09-09T00:00:00Z",
        end_at_utc: "2026-09-08T00:00:00Z",
      }),
    ).toThrow();
  });

  it("提交业务化加急命令，并用有界筛选读取服务端比较", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        jsonResponse({
          job_accepted_version: "cnc-demo-job-accepted.v1",
          job_id: "job-urgent-demo",
          job_kind: "URGENT_REPLAN",
          run_id: "run-demo",
          status: "QUEUED",
          replayed: false,
        }, 202),
      )
      .mockResolvedValueOnce(jsonResponse(comparisonView()));
    vi.stubGlobal("fetch", fetchMock);
    const api = createDemoApi();
    const command = {
      command_version: "cnc-demo-urgent-order-command.v1",
      expected_run_id: "run-demo",
      expected_base_version_id: "schedule-base-demo",
      route_template_id: "CNC-ROUTE-5",
      quantity: 5,
      due_at_local: "2026-09-09T18:00:00",
      priority_class: "URGENT",
      note: "固定演示插单",
    } as const;

    await api.submitUrgentOrder(command, "demo-urgent-idempotency-0001");
    await api.getComparison("replan-request-demo-1", {
      classifications: ["CHANGED", "ADDED", "CHANGED"],
      demand_order_ids: ["order-b", "order-a"],
      sort: "SHIFT_DESC",
      limit: 120,
    });

    const urgentInit = fetchMock.mock.calls[0]?.[1];
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/demo/v1/urgent-orders");
    expect(new Headers(urgentInit?.headers).get("Idempotency-Key")).toBe(
      "demo-urgent-idempotency-0001",
    );
    expect(JSON.parse(String(urgentInit?.body))).toEqual(command);
    const comparisonUrl = new URL(
      String(fetchMock.mock.calls[1]?.[0]),
      "http://demo.local",
    );
    expect(comparisonUrl.searchParams.getAll("classification")).toEqual([
      "ADDED",
      "CHANGED",
    ]);
    expect(comparisonUrl.searchParams.getAll("demand_order_id")).toEqual([
      "order-a",
      "order-b",
    ]);
    expect(comparisonUrl.searchParams.get("limit")).toBe("120");
  });

  it("比较查询拒绝空分类和超过前端展示上限的分页", () => {
    expect(() => buildComparisonQuery({ classifications: [] })).toThrow();
    expect(() => buildComparisonQuery({ limit: 201 })).toThrow();
  });
});
