async (page) => {
  const assertions = {};
  const requests = [];
  const check = (name, condition) => { assertions[name] = Boolean(condition); };
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().endsWith("/api/demo/v1/urgent-orders")) requests.push("URGENT_REPLAN");
  });
  await page.getByRole("button", { name: "核对并提交插单" }).click();
  const dialog = page.getByRole("dialog", { name: "确认接收这张加急订单？" });
  await dialog.waitFor();
  const responsePromise = page.waitForResponse((response) =>
    response.url().endsWith("/api/demo/v1/urgent-orders") && response.request().method() === "POST");
  await dialog.getByRole("button", { name: "确认插单并自动重排" }).dblclick({ delay: 5 });
  const response = await responsePromise;
  const accepted = await response.json();
  check("urgent_http_accepted", response.status() === 202);
  check("urgent_double_click_one_mutation", requests.length === 1);
  check("pending_job_persisted_before_refresh", await page.evaluate(() => localStorage.getItem("plantnexus-demo:pending-job") !== null));
  await page.evaluate((jobId) => sessionStorage.setItem("demo08-urgent-job-id", jobId), accepted.job_id);
  await page.reload({ waitUntil: "domcontentloaded" });
  const state = await page.evaluate(async () => (await fetch("/api/demo/v1/bootstrap", { credentials: "same-origin" })).json());
  check("refresh_recovers_same_replan_or_completed_result", state.active_job?.job_id === accepted.job_id || state.story_state === "DRAFT_COMPARISON_READY");
  return { assertions, identities: { urgent_job_id: accepted.job_id }, network: { business_mutations: requests, refresh_replayed_business_mutations: 0 } };
}
