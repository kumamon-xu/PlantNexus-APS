async (page) => {
  const assertions = {};
  const check = (name, condition) => { assertions[name] = Boolean(condition); };
  const payload = await page.evaluate(async () => {
    const state = await (await fetch("/api/demo/v1/bootstrap", { credentials: "same-origin" })).json();
    const query = new URLSearchParams();
    for (const value of ["ADDED", "CHANGED", "REMOVED_BY_FACT"]) query.append("classification", value);
    query.set("sort", "SHIFT_DESC");
    query.set("offset", "0");
    query.set("limit", "120");
    const response = await fetch(`/api/demo/v1/comparisons/${state.comparison_reference.request_id}?${query}`, { credentials: "same-origin" });
    return response.json();
  });
  check("comparison_added_five", payload.change_counts.added === 5);
  check("comparison_changed_present", payload.change_counts.changed > 0);
  check("comparison_unchanged_present", payload.change_counts.unchanged > 0);
  check("comparison_validator_pass", payload.provenance.validation_status === "PASS");
  check("comparison_page_bounded", payload.page.limit === 120);
  return { assertions, lifecycle: { comparison_change_counts: payload.change_counts } };
}
