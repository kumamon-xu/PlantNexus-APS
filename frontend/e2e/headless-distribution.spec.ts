import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { expect, test, type Page, type Route } from "@playwright/test";

const samples = resolve(import.meta.dirname, "../../schemas/samples");
const requestText = readFileSync(
  resolve(samples, "canonical-ingress-request.v1.synthetic.json"),
  "utf8",
);
const browserRequestText = requestText.replace(/\r\n/gu, "\n");
const accepted = JSON.parse(
  readFileSync(
    resolve(samples, "canonical-ingress-result.v1.accepted.synthetic.json"),
    "utf8",
  ),
) as Record<string, unknown>;
const created = JSON.parse(
  readFileSync(resolve(samples, "planning-run.v1.created.synthetic.json"), "utf8"),
) as Record<string, unknown>;
const completed = JSON.parse(
  readFileSync(
    resolve(samples, "planning-run.v1.completed.synthetic.json"),
    "utf8",
  ),
) as Record<string, unknown>;

interface WireCall {
  readonly method: string;
  readonly path: string;
  readonly body: string | null;
  readonly headers: Record<string, string>;
}

async function fulfillJson(
  route: Route,
  status: number,
  payload: unknown,
  correlationId: string,
): Promise<void> {
  await route.fulfill({
    status,
    contentType: "application/json",
    headers: {
      "Cache-Control": "no-store",
      "X-Correlation-Id": correlationId,
    },
    body: JSON.stringify(payload),
  });
}

async function installSuccessRuntime(page: Page): Promise<WireCall[]> {
  const calls: WireCall[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const headers = await request.allHeaders();
    const correlation = headers["x-correlation-id"] ?? "P8-MISSING-CORRELATION";
    calls.push({
      method: request.method(),
      path: url.pathname,
      body: request.postData(),
      headers,
    });
    if (request.method() === "POST" && url.pathname.endsWith("/planning-runs")) {
      await fulfillJson(route, 202, accepted, correlation);
      return;
    }
    if (url.pathname.endsWith("/status")) {
      await fulfillJson(route, 200, completed, correlation);
      return;
    }
    if (url.pathname.endsWith("/result")) {
      await fulfillJson(route, 200, completed, correlation);
      return;
    }
    await fulfillJson(route, 404, { message: "unregistered public operation" }, correlation);
  });
  return calls;
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    globalThis.localStorage.setItem("plantnexus.locale.v1", "en-US");
    const target = globalThis as typeof globalThis & {
      __PLANTNEXUS_APS_SESSION_PROVIDER__?: {
        getAccessToken(): Promise<string | null>;
      };
    };
    target.__PLANTNEXUS_APS_SESSION_PROVIDER__ = {
      async getAccessToken() {
        return "p8-browser-memory-token";
      },
    };
  });
});

test("packaged frontend completes create/status/result through the public Headless API", async ({
  page,
  context,
}) => {
  await context.addCookies([
    {
      name: "ambient_session",
      value: "must-not-be-forwarded",
      url: "http://127.0.0.1:4183",
    },
  ]);
  const calls = await installSuccessRuntime(page);
  await page.goto("/headless.html");

  await page.getByRole("textbox", { name: "Canonical JSON request" }).fill(browserRequestText);
  await page.getByRole("button", { name: "Submit to APS Runtime" }).click();
  await expect(page.getByText("PLANNING-RUN-P8-SYNTHETIC-001")).toBeVisible();
  await expect(page.getByText("EXTENSION-SET-NONE-P8-SAMPLE")).toBeVisible();

  await page.getByRole("button", { name: "Refresh status" }).click();
  await expect(page.getByText("COMPLETED")).toBeVisible();
  await page.getByRole("button", { name: "Load terminal result" }).click();

  await expect.poll(() => calls.length).toBe(3);
  expect(calls.map(({ method, path }) => `${method} ${path}`)).toEqual([
    "POST /api/v1/planning-runs",
    "GET /api/v1/planning-runs/PLANNING-RUN-P8-SYNTHETIC-001/status",
    "GET /api/v1/planning-runs/PLANNING-RUN-P8-SYNTHETIC-001/result",
  ]);
  expect(calls[0]?.body).toBe(browserRequestText);
  for (const call of calls) {
    expect(call.headers.authorization).toBe("Bearer p8-browser-memory-token");
    expect(call.headers.cookie).toBeUndefined();
  }
  expect(calls[1]?.headers["x-aps-tenant-id"]).toBe("TENANT-P8-SYNTHETIC");
  expect(calls[1]?.headers["x-aps-factory-id"]).toBe(
    "FACTORY-P8-SYNTHETIC-001",
  );
  expect(calls[1]?.headers["x-aps-planning-scope-id"]).toBe(
    "PLANNING-P8-SYNTHETIC-001",
  );
  const persistedCredentialKeys = await page.evaluate(() => [
    ...Object.keys(localStorage),
    ...Object.keys(sessionStorage),
  ].filter((key) => /auth|bearer|credential|session|token/iu.test(key)));
  expect(persistedCredentialKeys).toEqual([]);
});

test("renders cancellation only from server allowed_actions and submits exact CAS", async ({
  page,
}) => {
  const calls: WireCall[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const headers = await request.allHeaders();
    const correlation = headers["x-correlation-id"] ?? "P8-CANCEL";
    calls.push({
      method: request.method(),
      path: url.pathname,
      body: request.postData(),
      headers,
    });
    if (url.pathname.endsWith("/planning-runs")) {
      await fulfillJson(route, 202, accepted, correlation);
    } else {
      await fulfillJson(route, 200, created, correlation);
    }
  });
  await page.goto("/headless.html");
  await page.getByRole("textbox", { name: "Canonical JSON request" }).fill(browserRequestText);
  await page.getByRole("button", { name: "Submit to APS Runtime" }).click();
  await page.getByRole("button", { name: "Refresh status" }).click();
  await page.getByRole("textbox", { name: "Cancellation reason" }).fill("operator stop");
  await page.getByRole("button", { name: "Cancel run" }).click();

  await expect.poll(() => calls.length).toBe(3);
  expect(calls[2]?.path).toBe(
    "/api/v1/planning-runs/PLANNING-RUN-P8-SYNTHETIC-001/cancel",
  );
  expect(JSON.parse(calls[2]?.body ?? "{}")).toMatchObject({
    action_version: "planning-run-cancel-action.v1",
    expected_revision: 1,
    expected_state: "CREATED",
    expected_run_fingerprint:
      "sha256:ec30df6680a7a4d9c7d93eb3d93590591a3767caabb05a78dc3607bac052000b",
    reason: "operator stop",
  });
});

for (const [status, kind] of [
  [401, "authentication_required"],
  [403, "authorization_denied"],
  [409, "state_conflict"],
  [503, "unavailable"],
] as const) {
  test(`keeps HTTP ${status} visible as ${kind}`, async ({ page }) => {
    await page.route("**/api/v1/planning-runs", async (route) => {
      const correlation =
        (await route.request().allHeaders())["x-correlation-id"] ?? "P8-ERROR";
      await fulfillJson(route, status, { message: `bounded HTTP ${status}` }, correlation);
    });
    await page.goto("/headless.html");
    await page.getByRole("textbox", { name: "Canonical JSON request" }).fill(browserRequestText);
    await page.getByRole("button", { name: "Submit to APS Runtime" }).click();
    await expect(page.getByText(kind, { exact: true })).toBeVisible();
    await expect(page.getByText(`bounded HTTP ${status}`, { exact: true })).toBeVisible();
    await expect(page.getByText("Authoritative PlanningRun")).toHaveCount(0);
  });
}

test("rejects an unknown success contract version visibly", async ({ page }) => {
  const unknown = structuredClone(accepted);
  unknown.canonical_ingress_result_version = "canonical-ingress-result.v2";
  await page.route("**/api/v1/planning-runs", async (route) => {
    const correlation =
      (await route.request().allHeaders())["x-correlation-id"] ?? "P8-VERSION";
    await fulfillJson(route, 202, unknown, correlation);
  });
  await page.goto("/headless.html");
  await page.getByRole("textbox", { name: "Canonical JSON request" }).fill(browserRequestText);
  await page.getByRole("button", { name: "Submit to APS Runtime" }).click();
  await expect(page.getByText("version_error", { exact: true })).toBeVisible();
  await expect(page.getByText("VERSION_MISMATCH", { exact: true })).toBeVisible();
});

test("packaged bilingual surface is keyboard reachable and has no axe violations", async ({
  page,
}) => {
  await page.goto("/headless.html");
  await expect(page.locator("html")).toHaveAttribute("lang", "en-US");
  await page.getByRole("combobox", { name: "Language" }).selectOption("zh-CN");
  await expect(page.locator("html")).toHaveAttribute("lang", "zh-CN");
  await expect(page.getByText("可选 Headless API 前端", { exact: true })).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus")).not.toHaveCount(0);

  await page.addScriptTag({
    path: resolve(import.meta.dirname, "../node_modules/axe-core/axe.min.js"),
  });
  const violations = await page.evaluate(async () => {
    const axe = (globalThis as typeof globalThis & {
      axe: {
        run(
          root: Document,
          options: { rules: Record<string, { enabled: boolean }> },
        ): Promise<{ violations: unknown[] }>;
      };
    }).axe;
    const result = await axe.run(document, {
      rules: { "color-contrast": { enabled: false } },
    });
    return result.violations;
  });
  expect(violations).toEqual([]);
});
