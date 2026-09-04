async (page) => {
  const assertions = {};
  const check = (name, condition) => { assertions[name] = Boolean(condition); };
  const result = await page.evaluate(() => {
    const visible = (element) => { const s = getComputedStyle(element); const r = element.getBoundingClientRect(); return s.display !== "none" && s.visibility !== "hidden" && r.width > 0 && r.height > 0; };
    const levels = [...document.querySelectorAll("h1,h2,h3,h4,h5,h6")].filter(visible).map((element) => Number(element.tagName.slice(1)));
    const statuses = [...document.querySelectorAll('[role="status"],[aria-live]')].filter(visible);
    const badges = [...document.querySelectorAll(".change-badge")].filter(visible);
    return {
      heading_levels: levels,
      heading_jump_count: levels.filter((level, index) => index > 0 && level > levels[index - 1] + 1).length,
      main_count: document.querySelectorAll("main").length,
      navigation_landmark_count: document.querySelectorAll('nav,[role="navigation"]').length,
      status_count: statuses.length,
      status_without_text_count: statuses.filter((element) => !((element.textContent || "").trim() || element.getAttribute("aria-label"))).length,
      change_badge_count: badges.length,
      empty_change_badge_count: badges.filter((element) => !(element.textContent || "").trim()).length,
      draft_text: document.querySelector(".draft-boundary")?.textContent || "",
    };
  });
  check("heading_hierarchy_has_no_jump", result.heading_jump_count === 0);
  check("one_main_landmark", result.main_count === 1);
  check("navigation_landmark_present", result.navigation_landmark_count >= 1);
  check("live_statuses_have_text", result.status_without_text_count === 0);
  check("change_classifications_have_text", result.change_badge_count > 0 && result.empty_change_badge_count === 0);
  check("draft_boundary_not_color_only", result.draft_text.includes("未发布草稿") && result.draft_text.includes("保持不变"));
  delete result.draft_text;
  return { assertions, accessibility: result };
}
