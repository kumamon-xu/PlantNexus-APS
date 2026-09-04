async (page) => {
  const requests = [];
  const pageErrors = [];
  const requireValue = (condition, code) => {
    if (!condition) throw new Error(`D17_BROWSER_ASSERTION:${code}`);
  };
  page.on("pageerror", (error) => pageErrors.push(error.name || "Error"));
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().endsWith("/api/demo/v1/baseline-activations")
    ) {
      requests.push("ACTIVATE");
    }
  });
  await page.getByRole("button", { name: "设为仿真基线" }).click();
  const dialog = page.getByRole("dialog", { name: "设为当前仿真基线？" });
  await dialog.waitFor();
  const responsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/demo/v1/baseline-activations") &&
      response.request().method() === "POST",
  );
  await dialog.getByRole("button", { name: "确认并发布仿真基线" }).click();
  const response = await responsePromise;
  requireValue(response.status() === 200, "BASELINE_ACTIVATION_FAILED");
  await page.getByRole("button", { name: "插入加急订单" }).waitFor({ timeout: 30000 });
  const state = await page.evaluate(async () =>
    (await fetch("/api/demo/v1/bootstrap", { credentials: "same-origin" })).json(),
  );
  requireValue(state.story_state === "BASELINE_PUBLISHED", "BASELINE_STATE_NOT_READY");
  requireValue(state.schedule_version.state === "PUBLISHED", "BASELINE_NOT_PUBLISHED");
  requireValue(requests.length === 1, "ACTIVATION_MUTATION_COUNT_MISMATCH");
  requireValue(pageErrors.length === 0, "PAGE_ERROR_RECORDED");
  await page.evaluate(() => sessionStorage.setItem("demo09-baseline-sample-index", "0"));
  const browser = page.context().browser();
  return {
    status: "PASS",
    lifecycle: {
      run_id: state.run.run_id,
      published_schedule_version_id: state.current_publication.schedule_version_id,
      story_state: state.story_state,
    },
    mutation_kinds: requests,
    browser: {
      version: browser ? browser.version() : "unavailable",
      user_agent: await page.evaluate(() => navigator.userAgent),
      viewport: page.viewportSize(),
    },
  };
}
