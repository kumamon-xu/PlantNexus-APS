async (page) => {
  const requests = [];
  const requireValue = (condition, code) => {
    if (!condition) throw new Error(`D17_BROWSER_ASSERTION:${code}`);
  };
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().endsWith("/api/demo/v1/initial-plans")
    ) {
      requests.push("INITIAL_PLAN");
    }
  });
  const responsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/demo/v1/initial-plans") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "开始自动排产" }).click();
  const response = await responsePromise;
  requireValue(response.status() === 202, "INITIAL_PLAN_NOT_ACCEPTED");
  await page.getByRole("button", { name: "设为仿真基线" }).waitFor({ timeout: 180000 });
  requireValue(requests.length === 1, "INITIAL_MUTATION_COUNT_MISMATCH");
  return { status: "PASS", mutation_kinds: requests };
}
