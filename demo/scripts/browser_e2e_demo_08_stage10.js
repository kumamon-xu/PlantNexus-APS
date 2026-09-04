async (page) => {
  const assertions = {};
  const check = (name, condition) => { assertions[name] = Boolean(condition); };
  const contrast = await page.evaluate(() => {
    const targets = [
      ["hero_heading", ".hero-copy h1", ["#13262e", "#101d24"]],
      ["hero_lead", ".hero-lead", ["#13262e", "#101d24"]],
      ["primary_button", ".button--primary", null],
      ["simulation_badge", ".simulation-badge", ["#101d24"]],
      ["draft_boundary", ".draft-boundary strong", null],
      ["added_badge", ".change-badge--added", null],
      ["changed_badge", ".change-badge--changed", null],
      ["unchanged_badge", ".change-badge--unchanged", null],
    ];
    const rgb = (value) => { const found = value.match(/[\d.]+/g); return found?.slice(0, 3).map(Number) || null; };
    const hex = (value) => [1, 3, 5].map((start) => parseInt(value.slice(start, start + 2), 16));
    const luminance = (value) => {
      const parts = value.map((item) => { const c = item / 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; });
      return 0.2126 * parts[0] + 0.7152 * parts[1] + 0.0722 * parts[2];
    };
    const ratio = (a, b) => { const x = luminance(a); const y = luminance(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
    const background = (element) => {
      for (let current = element; current; current = current.parentElement) {
        const style = getComputedStyle(current).backgroundColor;
        const parsed = rgb(style);
        const alpha = (style.match(/[\d.]+/g) || [])[3];
        if (parsed && (alpha === undefined || Number(alpha) > 0.99)) return parsed;
      }
      return [255, 255, 255];
    };
    const output = {};
    for (const [name, selector, fixed] of targets) {
      let element = document.querySelector(selector);
      let rendered = true;
      if (!element && selector.startsWith(".change-badge--")) {
        element = document.createElement("span");
        element.className = `change-badge ${selector.slice(1)}`;
        element.textContent = "状态文字";
        element.style.position = "fixed";
        element.style.inset = "-100px auto auto -100px";
        document.body.append(element);
        rendered = false;
      }
      if (!element) { output[name] = { style_available: false, rendered: false, ratio: 0, threshold: 4.5, pass: false }; continue; }
      const style = getComputedStyle(element);
      const foreground = rgb(style.color);
      const backgrounds = fixed ? fixed.map(hex) : [background(element)];
      const size = parseFloat(style.fontSize);
      const weight = Number(style.fontWeight) || 400;
      const threshold = size >= 24 || (size >= 18.66 && weight >= 700) ? 3 : 4.5;
      const measured = foreground ? Math.min(...backgrounds.map((value) => ratio(foreground, value))) : 0;
      output[name] = { style_available: true, rendered, ratio: Number(measured.toFixed(2)), threshold, pass: measured + 0.001 >= threshold };
      if (!rendered) element.remove();
    }
    return output;
  });
  check("critical_text_contrast_passes", Object.values(contrast).every((item) => item.pass));
  return { assertions, contrast };
}
