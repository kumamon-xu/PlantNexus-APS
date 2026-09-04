async (page) => {
  const assertions = {};
  const requests = [];
  const check = (name, condition) => { assertions[name] = Boolean(condition); };
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().endsWith("/api/demo/v1/initial-plans")) requests.push("INITIAL_PLAN");
  });
  const responsePromise = page.waitForResponse((response) =>
    response.url().endsWith("/api/demo/v1/initial-plans") && response.request().method() === "POST");
  await page.getByRole("button", { name: "开始自动排产" }).click();
  const response = await responsePromise;
  const accepted = await response.json();
  check("initial_plan_http_accepted", response.status() === 202);
  await page.getByRole("button", { name: "设为仿真基线" }).waitFor({ timeout: 90000 });
  const trigger = page.getByRole("button", { name: "重置演示" });
  await trigger.click();
  const dialog = page.getByRole("dialog", { name: "重置当前演示运行？" });
  await dialog.waitFor();
  check("reset_dialog_initial_focus", (await page.evaluate(() => document.activeElement?.textContent?.trim())) === "确认重置");
  await page.keyboard.press("Tab");
  check("reset_dialog_tab_wraps", (await page.evaluate(() => document.activeElement?.textContent?.trim())) === "取消");
  await page.keyboard.press("Shift+Tab");
  check("reset_dialog_shift_tab_wraps", (await page.evaluate(() => document.activeElement?.textContent?.trim())) === "确认重置");
  await page.keyboard.press("Escape");
  await dialog.waitFor({ state: "detached" });
  check("reset_dialog_restores_focus", await trigger.evaluate((element) => element === document.activeElement));
  check("cancelled_reset_has_no_mutation", requests.length === 1);
  return { assertions, identities: { initial_plan_job_id: accepted.job_id }, network: { business_mutations: requests } };
}
