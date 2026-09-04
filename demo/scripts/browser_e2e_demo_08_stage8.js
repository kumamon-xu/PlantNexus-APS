async (page) => {
  const assertions = {};
  const check = (name, condition) => { assertions[name] = Boolean(condition); };
  const allButton = page.getByRole("button", { name: "全部工序" });
  await allButton.click();
  await page.locator(".change-badge--unchanged").first().waitFor({ timeout: 30000 });
  check("all_filter_aria_pressed", (await allButton.getAttribute("aria-pressed")) === "true");
  check("unchanged_state_has_text", (await page.locator(".change-badge--unchanged").first().innerText()).trim() === "保持不变");
  const accessibility = await page.evaluate(() => {
    const visible = (element) => {
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
    };
    const controls = [...document.querySelectorAll('a[href],button,input,select,textarea,summary,[role="button"],[tabindex]:not([tabindex="-1"])')]
      .filter((element) => visible(element) && !element.disabled);
    const name = (element) => {
      const refs = (element.getAttribute("aria-labelledby") || "").split(/\s+/).filter(Boolean)
        .map((id) => document.getElementById(id)?.textContent || "").join(" ");
      const label = element.id ? document.querySelector(`label[for="${CSS.escape(element.id)}"]`)?.textContent || "" : "";
      return (element.getAttribute("aria-label") || refs || label || element.closest("label")?.textContent || element.getAttribute("title") || element.textContent || "").trim();
    };
    const ids = [...document.querySelectorAll("[id]")].map((element) => element.id);
    const broken = [];
    for (const element of document.querySelectorAll("[aria-labelledby],[aria-describedby],[aria-controls]")) {
      for (const attribute of ["aria-labelledby", "aria-describedby", "aria-controls"]) {
        for (const id of (element.getAttribute(attribute) || "").split(/\s+/).filter(Boolean)) {
          if (!document.getElementById(id)) broken.push(`${attribute}:${id}`);
        }
      }
    }
    return {
      interactive_count: controls.length,
      unnamed_interactive_count: controls.filter((element) => !name(element)).length,
      duplicate_ids: [...new Set(ids.filter((id, index) => ids.indexOf(id) !== index))],
      broken_aria_references: broken,
    };
  });
  check("all_interactive_controls_named", accessibility.unnamed_interactive_count === 0);
  check("document_ids_unique", accessibility.duplicate_ids.length === 0);
  check("aria_references_resolve", accessibility.broken_aria_references.length === 0);
  return { assertions, accessibility };
}
