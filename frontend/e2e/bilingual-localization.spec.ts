import { createHash } from "node:crypto";

import { expect, test, type Route } from "@playwright/test";

function canonical(value: unknown): string {
  if (value === null || typeof value === "boolean" || typeof value === "string") {
    return JSON.stringify(value);
  }
  if (typeof value === "number") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  const object = value as Record<string, unknown>;
  return `{${Object.keys(object).sort().map((key) => `${JSON.stringify(key)}:${canonical(object[key])}`).join(",")}}`;
}

function sha(value: unknown): string {
  return `sha256:${createHash("sha256").update(canonical(value)).digest("hex")}`;
}

interface WireObservation {
  readonly method: string;
  readonly view: unknown;
  readonly hasLocaleField: boolean;
}

async function respondWithDataHealth(route: Route, observations: WireObservation[]) {
  const request = route.request();
  const url = new URL(request.url());
  const query = JSON.parse(url.searchParams.get("query") ?? "{}") as Record<string, unknown>;
  observations.push({
    method: request.method(),
    view: query.view,
    hasLocaleField: Object.keys(query).some((key) => /locale|language/iu.test(key)),
  });
  const payload = {
    status: "HEALTHY",
    checked_at_utc: "2026-08-27T00:00:00Z",
  };
  const item = {
    item_id: "data-health-i18n-e2e-001",
    item_type: "DATA_HEALTH",
    payload,
    payload_fingerprint: sha(payload),
  };
  const reference = {
    item_id: item.item_id,
    item_type: item.item_type,
    payload_fingerprint: item.payload_fingerprint,
  };
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      document: {
        ...query,
        direction: "RESULT",
        result: {
          result_version: "workspace-query-result.v1",
          found: true,
          authoritative_schedule_version: null,
          lineage: null,
          items: [reference],
          next_cursor: null,
          observed_count: 1,
          allowed_actions: [],
          freshness: "FRESH",
          generated_at_utc: "2026-08-27T00:00:00Z",
        },
      },
      items: [item],
      collection_fingerprint: sha({ items: [reference] }),
      source_fingerprint: null,
      correlation_id: query.correlation_id,
    }),
  });
}

test("defaults to zh-CN, switches to en-US, restores preference and keeps the read wire locale-neutral", async ({ page }) => {
  const observations: WireObservation[] = [];
  await page.route("**/api/v1/workspace/data-health?**", async (route) => {
    await respondWithDataHealth(route, observations);
  });

  await page.goto("/planning/data-health");
  await expect(page.locator("html")).toHaveAttribute("lang", "zh-CN");
  await expect(page.getByRole("heading", { name: "数据健康" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "计划工作区导航" })).toBeVisible();
  await expect(page.getByText("HEALTHY", { exact: false })).toBeVisible();
  await expect(page.getByText("2026-08-27T00:00:00Z", { exact: true })).toBeVisible();

  await page.getByRole("combobox", { name: "语言" }).click();
  await page.getByText("English", { exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "en-US");
  await expect(page.getByRole("heading", { name: "Data health" })).toBeVisible();
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("lang", "en-US");
  await expect(page.getByRole("heading", { name: "Data health" })).toBeVisible();

  expect(observations.length).toBeGreaterThanOrEqual(2);
  for (const observation of observations) {
    expect(observation).toEqual({
      method: "GET",
      view: "DATA_HEALTH",
      hasLocaleField: false,
    });
  }
});
