async (page) => {
  const assertions = {};
  const check = (name, condition) => { assertions[name] = Boolean(condition); };
  await page.emulateMedia({ reducedMotion: "reduce" });
  const reducedMotion = await page.evaluate(() => {
    const element = document.querySelector(".status-orb--live") || document.querySelector(".timeline-bar--new");
    const style = element ? getComputedStyle(element) : null;
    return {
      media_matches: matchMedia("(prefers-reduced-motion: reduce)").matches,
      animation_duration: style?.animationDuration || "",
      animation_iteration_count: style?.animationIterationCount || "",
      transition_duration: style?.transitionDuration || "",
      scroll_behavior: getComputedStyle(document.documentElement).scrollBehavior,
    };
  });
  check("reduced_motion_media_matches", reducedMotion.media_matches);
  check("reduced_motion_css_applied", reducedMotion.scroll_behavior === "auto" && (["0.00001s", "1e-05s"].includes(reducedMotion.animation_duration) || ["0.00001s", "1e-05s"].includes(reducedMotion.transition_duration)));
  await page.emulateMedia({ reducedMotion: "no-preference" });
  const layouts = {};
  for (const [label, width, height] of [["wide", 1440, 900], ["compact", 1024, 768]]) {
    await page.setViewportSize({ width, height });
    await page.waitForTimeout(100);
    layouts[label] = await page.evaluate(() => ({
      viewport_width: document.documentElement.clientWidth,
      viewport_height: window.innerHeight,
      scroll_width: document.documentElement.scrollWidth,
      body_scroll_width: document.body.scrollWidth,
      horizontal_overflow_px: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth, document.body.scrollWidth - document.documentElement.clientWidth),
    }));
  }
  check("wide_has_no_page_overflow", layouts.wide.horizontal_overflow_px <= 1);
  check("compact_has_no_page_overflow", layouts.compact.horizontal_overflow_px <= 1);
  await page.setViewportSize({ width: 1440, height: 900 });
  const changed = page.getByRole("button", { name: "仅看变化" });
  await changed.click();
  await page.locator(".change-badge--added").first().waitFor({ timeout: 30000 });
  check("changed_filter_aria_pressed", (await changed.getAttribute("aria-pressed")) === "true");
  return { assertions, reduced_motion: reducedMotion, layouts };
}
