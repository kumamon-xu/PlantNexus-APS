async (page) => {
  const state = await page.evaluate(async () =>
    (await fetch("/api/demo/v1/bootstrap", { credentials: "same-origin" })).json(),
  );
  return {
    status: "PASS",
    ready: state.story_state === "DRAFT_COMPARISON_READY",
    story_state: state.story_state,
  };
}
