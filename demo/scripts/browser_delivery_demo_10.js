async (page) => {
  const pageErrors = [];
  const consoleErrors = [];
  const failedResponses = [];
  const requireValue = (condition, code) => {
    if (!condition) throw new Error(`D18_BROWSER_ASSERTION:${code}`);
  };

  page.on("pageerror", (error) => pageErrors.push(error.name));
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push("console-error");
  });
  page.on("response", (response) => {
    if (response.status() >= 500) failedResponses.push(response.status());
  });

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.reload({ waitUntil: "networkidle", timeout: 60000 });
  await page
    .getByRole("heading", { name: "工厂已初始化", exact: true })
    .waitFor({ timeout: 30000 });

  const htmlLanguage = await page.locator("html").getAttribute("lang");
  const bodyText = await page.locator("body").innerText();
  const bootstrap = await page.evaluate(async () => {
    const response = await fetch("/api/demo/v1/bootstrap", {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) return { http_status: response.status };
    return response.json();
  });
  const cookies = await page.context().cookies();
  const localSessionCookies = cookies.filter(
    (cookie) =>
      cookie.httpOnly === true &&
      cookie.sameSite === "Strict" &&
      cookie.domain === "127.0.0.1",
  );

  requireValue(htmlLanguage === "zh-CN", "HTML_LANGUAGE_NOT_ZH_CN");
  requireValue(bodyText.includes("CNC 精密机加工演示"), "INDUSTRY_COPY_MISSING");
  requireValue(bodyText.includes("仿真环境 · 非生产"), "SIMULATION_BADGE_MISSING");
  requireValue(bodyText.includes("固定种子 20260902"), "FIXED_SEED_COPY_MISSING");
  requireValue(bodyText.includes("132"), "ORDER_COUNT_NOT_VISIBLE");
  requireValue(bodyText.includes("610"), "OPERATION_COUNT_NOT_VISIBLE");
  requireValue(bodyText.includes("24"), "RESOURCE_COUNT_NOT_VISIBLE");
  requireValue(bootstrap.bootstrap_version === "cnc-demo-bootstrap.v1", "BOOTSTRAP_VERSION");
  requireValue(bootstrap.story_state === "INITIALIZED", "STORY_STATE");
  requireValue(bootstrap.simulation_only === true, "SIMULATION_BOUNDARY");
  requireValue(bootstrap.production_authority === false, "PRODUCTION_BOUNDARY");
  requireValue(bootstrap.scenario_manifest?.profile_name === "showcase", "PROFILE_NAME");
  requireValue(bootstrap.scenario_manifest?.scenario_id === "CNC-DEMO-SHOWCASE", "SCENARIO_ID");
  requireValue(bootstrap.scenario_manifest?.seed === 20260902, "SCENARIO_SEED");
  requireValue(
    bootstrap.scenario_manifest?.source_counts?.demand_orders === 132,
    "ORDER_COUNT",
  );
  requireValue(
    bootstrap.scenario_manifest?.source_counts?.routing_operations === 610,
    "OPERATION_COUNT",
  );
  requireValue(
    bootstrap.scenario_manifest?.source_counts?.resources === 24,
    "RESOURCE_COUNT",
  );
  requireValue(localSessionCookies.length === 1, "LOCAL_SESSION_COOKIE_POLICY");
  requireValue(pageErrors.length === 0, "PAGE_ERROR");
  requireValue(consoleErrors.length === 0, "CONSOLE_ERROR");
  requireValue(failedResponses.length === 0, "SERVER_RESPONSE_ERROR");

  return {
    status: "PASS",
    locale: htmlLanguage,
    story_state: bootstrap.story_state,
    profile_name: bootstrap.scenario_manifest.profile_name,
    scenario_id: bootstrap.scenario_manifest.scenario_id,
    run_id: bootstrap.scenario_manifest.run_id,
    seed: bootstrap.scenario_manifest.seed,
    counts: { orders: 132, operations: 610, resources: 24 },
    simulation_only: bootstrap.simulation_only,
    production_authority: bootstrap.production_authority,
    local_session_cookie_policy: "HTTP_ONLY_SAME_SITE_STRICT",
    page_error_count: pageErrors.length,
    console_error_count: consoleErrors.length,
    server_error_response_count: failedResponses.length,
  };
}
