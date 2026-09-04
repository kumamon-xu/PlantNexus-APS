async (page) => {
  const assertions = {};
  const requests = [];
  const check = (name, condition) => { assertions[name] = Boolean(condition); };
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().endsWith("/api/demo/v1/baseline-activations")) requests.push("ACTIVATE");
  });
  await page.getByRole("button", { name: "设为仿真基线" }).click();
  const dialog = page.getByRole("dialog", { name: "设为当前仿真基线？" });
  await dialog.waitFor();
  const responsePromise = page.waitForResponse((response) =>
    response.url().endsWith("/api/demo/v1/baseline-activations") && response.request().method() === "POST");
  await dialog.getByRole("button", { name: "确认并发布仿真基线" }).click();
  const response = await responsePromise;
  check("activation_http_succeeded", response.status() === 200);
  await page.getByRole("button", { name: "插入加急订单" }).waitFor({ timeout: 30000 });
  const published = await page.evaluate(async () => (await fetch("/api/demo/v1/bootstrap", { credentials: "same-origin" })).json());
  check("published_story_ready", published.story_state === "BASELINE_PUBLISHED");
  check("published_schedule_state", published.schedule_version.state === "PUBLISHED");
  check("activation_one_mutation", requests.length === 1);
  return {
    assertions,
    identities: { run_id: published.run.run_id, published_schedule_version_id: published.current_publication.schedule_version_id },
    network: { business_mutations: requests },
  };
}
