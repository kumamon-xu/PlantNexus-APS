async (page) => {
  const responses = [];
  const pageErrors = [];
  const requireValue = (condition, code) => {
    if (!condition) throw new Error(`D17_BROWSER_ASSERTION:${code}`);
  };
  page.on("pageerror", (error) => pageErrors.push(error.name || "Error"));
  page.on("response", (response) => {
    const address = response.url();
    const marker = "/api/demo/v1/";
    const markerIndex = address.indexOf(marker);
    if (markerIndex >= 0) {
      responses.push({
        method: response.request().method(),
        path: address.slice(markerIndex),
        status: response.status(),
      });
    }
  });
  const index = await page.evaluate(() =>
    Number(sessionStorage.getItem("demo09-comparison-sample-index") || "0"),
  );
  const role = index === 0 ? "warmup" : "measured";
  const sequence = index === 0 ? 1 : index;
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.locator('[data-testid="schedule-workspace"] .workspace-summary').waitFor({
    state: "visible",
    timeout: 60000,
  });
  await page.locator('[data-testid="comparison-workspace"] .comparison-list').waitFor({
    state: "visible",
    timeout: 60000,
  });
  await page.evaluate(async () => {
    if (document.fonts) await document.fonts.ready;
  });
  const metrics = await page.evaluate(() => {
    const navigation = performance.getEntriesByType("navigation")[0];
    const api = performance
      .getEntriesByType("resource")
      .filter((entry) => new URL(entry.name).pathname.startsWith("/api/demo/v1/"))
      .map((entry) => {
        const url = new URL(entry.name);
        return {
          path: `${url.pathname}${url.search}`,
          initiator_type: entry.initiatorType,
          duration_milliseconds: Number(entry.duration.toFixed(3)),
          response_end_milliseconds: Number(entry.responseEnd.toFixed(3)),
          transfer_bytes: entry.transferSize,
          encoded_body_bytes: entry.encodedBodySize,
          decoded_body_bytes: entry.decodedBodySize,
        };
      });
    return {
      ready_milliseconds: Number(performance.now().toFixed(3)),
      navigation_dom_content_loaded_milliseconds: navigation
        ? Number(navigation.domContentLoadedEventEnd.toFixed(3))
        : null,
      navigation_load_event_milliseconds: navigation
        ? Number(navigation.loadEventEnd.toFixed(3))
        : null,
      api_max_milliseconds: api.length
        ? Math.max(...api.map((entry) => entry.duration_milliseconds))
        : null,
      api_resources: api,
      dom: {
        element_count: document.getElementsByTagName("*").length,
        document_html_bytes: new TextEncoder().encode(document.documentElement.outerHTML).length,
        viewport_width: window.innerWidth,
        viewport_height: window.innerHeight,
        document_scroll_width: document.documentElement.scrollWidth,
        document_scroll_height: document.documentElement.scrollHeight,
      },
      language: document.documentElement.lang,
      schedule_workspace_visible: Boolean(
        document.querySelector('[data-testid="schedule-workspace"] .workspace-summary'),
      ),
      comparison_workspace_visible: Boolean(
        document.querySelector('[data-testid="comparison-workspace"] .comparison-list'),
      ),
    };
  });
  for (const fragment of ["/bootstrap", "/factory", "/versions/", "/comparisons/"]) {
    requireValue(
      responses.some((response) => response.path.includes(fragment)),
      `API_RESPONSE_MISSING_${fragment.replaceAll("/", "_").toUpperCase()}`,
    );
  }
  requireValue(responses.every((response) => response.status < 400), "API_RESPONSE_FAILED");
  requireValue(metrics.language === "zh-CN", "DOCUMENT_LANGUAGE_NOT_ZH_CN");
  requireValue(metrics.schedule_workspace_visible, "SCHEDULE_WORKSPACE_NOT_READY");
  requireValue(metrics.comparison_workspace_visible, "COMPARISON_WORKSPACE_NOT_READY");
  requireValue(metrics.api_max_milliseconds !== null, "RESOURCE_TIMING_MISSING");
  requireValue(pageErrors.length === 0, "PAGE_ERROR_RECORDED");
  await page.evaluate(
    (nextIndex) => sessionStorage.setItem("demo09-comparison-sample-index", String(nextIndex)),
    index + 1,
  );
  return {
    status: "PASS",
    sample: {
      sample_id: `draft_comparison_ready-${role}-${String(sequence).padStart(2, "0")}`,
      state: "DRAFT_COMPARISON_READY",
      role,
      sequence,
      status: "PASS",
      ...metrics,
      responses,
    },
  };
}
