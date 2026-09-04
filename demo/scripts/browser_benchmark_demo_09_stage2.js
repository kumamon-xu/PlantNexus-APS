async (page) => {
  const requests = [];
  const requireValue = (condition, code) => {
    if (!condition) throw new Error(`D17_BROWSER_ASSERTION:${code}`);
  };
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().endsWith("/api/demo/v1/urgent-orders")
    ) {
      requests.push("URGENT_REPLAN");
    }
  });
  await page.getByRole("button", { name: "插入加急订单" }).click();
  await page.getByRole("heading", { name: "插入加急订单" }).waitFor();
  await page.locator('input[value="CNC-ROUTE-5"]').check();
  await page.getByRole("spinbutton", { name: /订单数量/ }).fill("5");
  await page.locator('input[type="datetime-local"]').fill("2026-09-09T18:00");
  await page.getByRole("combobox", { name: "优先级" }).selectOption("URGENT");
  await page.getByRole("textbox", { name: /演示备注/ }).fill("Showcase 固定加急精密套筒");
  await page.getByRole("button", { name: "核对并提交插单" }).click();
  const dialog = page.getByRole("dialog", { name: "确认接收这张加急订单？" });
  await dialog.waitFor();
  const responsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/demo/v1/urgent-orders") &&
      response.request().method() === "POST",
  );
  await dialog.getByRole("button", { name: "确认插单并自动重排" }).click();
  const response = await responsePromise;
  const accepted = await response.json();
  const command = response.request().postDataJSON();
  requireValue(response.status() === 202, "URGENT_REPLAN_NOT_ACCEPTED");
  requireValue(command.route_template_id === "CNC-ROUTE-5", "URGENT_ROUTE_MISMATCH");
  requireValue(command.quantity === 5, "URGENT_QUANTITY_MISMATCH");
  requireValue(command.due_at_local === "2026-09-09T18:00:00", "URGENT_DUE_MISMATCH");
  requireValue(command.priority_class === "URGENT", "URGENT_PRIORITY_MISMATCH");
  requireValue(command.note === "Showcase 固定加急精密套筒", "URGENT_NOTE_MISMATCH");
  requireValue(requests.length === 1, "URGENT_MUTATION_COUNT_MISMATCH");
  await page.evaluate((jobId) => sessionStorage.setItem("demo09-urgent-job-id", jobId), accepted.job_id);
  await page.reload({ waitUntil: "domcontentloaded" });
  return {
    status: "PASS",
    fixed_urgent_fixture: {
      route_template_id: command.route_template_id,
      quantity: command.quantity,
      due_at_local: command.due_at_local,
      timezone: "Asia/Shanghai",
      priority_class: command.priority_class,
      note: command.note,
    },
    mutation_kinds: requests,
  };
}
