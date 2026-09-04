async (page) => {
  const assertions = {};
  const requests = [];
  const check = (name, condition) => { assertions[name] = Boolean(condition); };
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().endsWith("/api/demo/v1/resets")) requests.push("RESET");
  });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: "等待初始化" }).waitFor({ timeout: 30000 });
  check("document_language_zh_cn", (await page.locator("html").getAttribute("lang")) === "zh-CN");
  await page.keyboard.press("Tab");
  check("skip_link_first_keyboard_target", (await page.evaluate(() => document.activeElement?.textContent?.trim())) === "跳到主要内容");
  await page.keyboard.press("Enter");
  check("skip_link_focuses_main", (await page.evaluate(() => document.activeElement?.id)) === "main-content");
  const responsePromise = page.waitForResponse((response) =>
    response.url().endsWith("/api/demo/v1/resets") && response.request().method() === "POST");
  await page.getByRole("button", { name: "初始化演示工厂" }).dblclick({ delay: 5 });
  const response = await responsePromise;
  const accepted = await response.json();
  check("reset_http_accepted", response.status() === 202);
  await page.getByRole("button", { name: "开始自动排产" }).waitFor({ timeout: 90000 });
  check("reset_double_click_one_mutation", requests.length === 1);
  return { assertions, identities: { reset_job_id: accepted.job_id }, network: { business_mutations: requests } };
}
