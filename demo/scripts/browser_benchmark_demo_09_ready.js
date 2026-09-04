async (page) => {
  const pageErrors = [];
  const requireValue = (condition, code) => {
    if (!condition) throw new Error(`D17_BROWSER_ASSERTION:${code}`);
  };
  page.on("pageerror", (error) => pageErrors.push(error.name || "Error"));
  await page.getByRole("heading", { name: "插单前后版本比较" }).waitFor({ timeout: 10000 });
  await page.getByText("独立校验通过").first().waitFor({ timeout: 10000 });
  await page.locator('[data-testid="comparison-workspace"] .comparison-list').waitFor({
    state: "visible",
    timeout: 10000,
  });
  const state = await page.evaluate(async () =>
    (await fetch("/api/demo/v1/bootstrap", { credentials: "same-origin" })).json(),
  );
  const jobId = await page.evaluate(() => sessionStorage.getItem("demo09-urgent-job-id"));
  const job = await page.evaluate(
    async (value) =>
      (await fetch(`/api/demo/v1/jobs/${value}`, { credentials: "same-origin" })).json(),
    jobId,
  );
  const query = [
    "classification=ADDED",
    "classification=CHANGED",
    "classification=UNCHANGED",
    "classification=REMOVED_BY_FACT",
    "sort=OPERATION_ASC",
    "offset=0",
    "limit=120",
  ].join("&");
  const comparison = await page.evaluate(
    async ({ requestId, parameters }) =>
      (
        await fetch(`/api/demo/v1/comparisons/${requestId}?${parameters}`, {
          credentials: "same-origin",
        })
      ).json(),
    { requestId: state.comparison_reference.request_id, parameters: query },
  );
  requireValue(state.story_state === "DRAFT_COMPARISON_READY", "COMPARISON_STATE_NOT_READY");
  requireValue(state.schedule_version.state === "DRAFT", "REPLAN_RESULT_NOT_DRAFT");
  requireValue(job.status === "SUCCEEDED", "URGENT_JOB_NOT_SUCCEEDED");
  requireValue(job.result.validation_status === "PASS", "URGENT_VALIDATOR_NOT_PASS");
  requireValue(comparison.change_counts.added === 5, "COMPARISON_ADDED_COUNT_MISMATCH");
  requireValue(comparison.change_counts.changed > 0, "COMPARISON_CHANGED_MISSING");
  requireValue(comparison.change_counts.unchanged > 0, "COMPARISON_UNCHANGED_MISSING");
  requireValue(
    state.current_publication.schedule_version_id ===
      state.comparison_reference.before_schedule_version_id,
    "CURRENT_PUBLICATION_CHANGED",
  );
  requireValue(pageErrors.length === 0, "PAGE_ERROR_RECORDED");
  await page.evaluate(() => sessionStorage.setItem("demo09-comparison-sample-index", "0"));
  return {
    status: "PASS",
    lifecycle: {
      run_id: state.run.run_id,
      published_schedule_version_id: state.comparison_reference.before_schedule_version_id,
      draft_schedule_version_id: state.comparison_reference.after_schedule_version_id,
      replan_request_id: state.comparison_reference.request_id,
      urgent_job_id: jobId,
      solver_status: job.result.solver_status,
      validation_status: job.result.validation_status,
      current_publication_unchanged: true,
      change_counts: comparison.change_counts,
    },
  };
}
