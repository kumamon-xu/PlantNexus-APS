async (page) => {
  const assertions = {};
  const check = (name, condition) => { assertions[name] = Boolean(condition); };
  const heading = page.getByRole("heading", { name: "插单前后版本比较" });
  await heading.waitFor({ timeout: 120000 });
  check("comparison_heading_receives_focus", await heading.evaluate((element) => element === document.activeElement));
  await page.getByText("独立校验通过").first().waitFor();
  const state = await page.evaluate(async () => (await fetch("/api/demo/v1/bootstrap", { credentials: "same-origin" })).json());
  const jobId = await page.evaluate(() => sessionStorage.getItem("demo08-urgent-job-id"));
  const job = await page.evaluate(async (id) => (await fetch(`/api/demo/v1/jobs/${id}`, { credentials: "same-origin" })).json(), jobId);
  check("final_story_comparison_ready", state.story_state === "DRAFT_COMPARISON_READY");
  check("final_schedule_is_draft", state.schedule_version.state === "DRAFT");
  check("current_publication_unchanged", state.current_publication.schedule_version_id === state.comparison_reference.before_schedule_version_id);
  check("draft_matches_comparison_reference", state.schedule_version.schedule_version_id === state.comparison_reference.after_schedule_version_id);
  check("urgent_job_succeeded", job.status === "SUCCEEDED");
  check("urgent_job_validator_pass", job.result.validation_status === "PASS");
  check("urgent_job_has_ten_stages", job.stages.length === 10);
  return {
    assertions,
    lifecycle: {
      urgent_job_id: jobId,
      run_id: state.run.run_id,
      story_state: state.story_state,
      before_schedule_version_id: state.comparison_reference.before_schedule_version_id,
      after_schedule_version_id: state.comparison_reference.after_schedule_version_id,
      request_id: state.comparison_reference.request_id,
      change_report_id: state.comparison_reference.change_report_id,
      solver_status: job.result.solver_status,
      validation_status: job.result.validation_status,
      job_stage_count: job.stages.length,
      current_publication_unchanged: true,
    },
  };
}
