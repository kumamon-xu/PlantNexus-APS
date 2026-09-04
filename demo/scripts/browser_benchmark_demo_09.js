async (page) => {
  const requests = [];
  const requireValue = (condition, code) => {
    if (!condition) throw new Error(`D17_BROWSER_ASSERTION:${code}`);
  };
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().endsWith("/api/demo/v1/resets")
    ) {
      requests.push("RESET");
    }
  });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.getByRole("button", { name: "初始化演示工厂" }).waitFor({ timeout: 30000 });
  const responsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/demo/v1/resets") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "初始化演示工厂" }).click();
  const response = await responsePromise;
  requireValue(response.status() === 202, "RESET_NOT_ACCEPTED");
  await page.getByRole("button", { name: "开始自动排产" }).waitFor({ timeout: 120000 });
  requireValue(requests.length === 1, "RESET_MUTATION_COUNT_MISMATCH");
  return { status: "PASS", mutation_kinds: requests };
}
