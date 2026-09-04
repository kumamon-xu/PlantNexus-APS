async (page) => {
  const assertions = {};
  const check = (name, condition) => { assertions[name] = Boolean(condition); };
  const browser = await page.evaluate(async () => {
    const first = await fetch("/api/demo/v1/bootstrap", { credentials: "same-origin" });
    const bootstrapText = await first.text();
    const bootstrap = JSON.parse(bootstrapText);
    const query = new URLSearchParams();
    for (const value of ["ADDED", "CHANGED", "REMOVED_BY_FACT"]) query.append("classification", value);
    query.set("sort", "SHIFT_DESC"); query.set("offset", "0"); query.set("limit", "120");
    const second = await fetch(`/api/demo/v1/comparisons/${bootstrap.comparison_reference.request_id}?${query}`, { credentials: "same-origin" });
    const comparisonText = await second.text();
    const text = document.body.innerText;
    return {
      dom_node_count: document.querySelectorAll("*").length,
      observed_resource_request_count: performance.getEntriesByType("resource").length,
      response_sizes_bytes: { bootstrap: new TextEncoder().encode(bootstrapText).length, comparison: new TextEncoder().encode(comparisonText).length },
      visible_text_has_credential_marker: text.includes("Authorization:") || text.includes("demo_session=") || text.includes("session.token"),
      visible_text_has_internal_path: /[A-Za-z]:\\\\[^\n]+/.test(text),
      visible_text_has_traceback: text.includes("Traceback (most recent call last)"),
    };
  });
  const cookies = (await page.context().cookies()).map((cookie) => ({ name: cookie.name, domain: cookie.domain, path: cookie.path, http_only: cookie.httpOnly, secure: cookie.secure, same_site: cookie.sameSite, value_recorded: false }));
  browser.cookies = cookies;
  check("single_http_only_session_cookie", cookies.length === 1 && cookies[0].http_only);
  check("session_cookie_same_site_strict", cookies.length === 1 && cookies[0].same_site === "Strict");
  check("credential_markers_absent_from_visible_text", !browser.visible_text_has_credential_marker);
  check("internal_paths_absent_from_visible_text", !browser.visible_text_has_internal_path);
  check("traceback_absent_from_visible_text", !browser.visible_text_has_traceback);
  check("response_sizes_recorded", browser.response_sizes_bytes.bootstrap > 0 && browser.response_sizes_bytes.comparison > 0);
  check("dom_count_recorded", browser.dom_node_count > 0);
  return { assertions, browser };
}
