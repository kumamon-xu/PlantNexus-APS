import {
  formatInteger,
  formatNumber,
  formatSeconds,
  formatUtc,
  formatUtilization,
} from "../src/i18n/formatters";

describe("TEST-FRONTEND-I18N-001 locale formatting and raw evidence", () => {
  it.each(["zh-CN", "en-US"] as const)("formats UTC in %s and preserves exact raw UTC", (locale) => {
    const value = "2026-08-25T03:04:05Z";
    const formatted = formatUtc(value, locale);
    expect(formatted.display).toBe(
      new Intl.DateTimeFormat(locale, {
        dateStyle: "medium",
        timeStyle: "medium",
        timeZone: "UTC",
      }).format(Date.parse(value)),
    );
    expect(formatted.raw).toBe(value);
  });

  it("does not invent a timezone or hide malformed raw time", () => {
    expect(formatUtc("2026-08-25T03:04:05+08:00", "zh-CN")).toEqual({
      display: "未知（2026-08-25T03:04:05+08:00）",
      raw: "2026-08-25T03:04:05+08:00",
    });
  });

  it.each(["zh-CN", "en-US"] as const)("uses Intl in %s and retains raw numbers", (locale) => {
    expect(formatNumber(12345.67, locale)).toEqual({
      display: new Intl.NumberFormat(locale).format(12345.67),
      raw: "12345.67",
    });
    expect(formatInteger(14400, locale).raw).toBe("14400");
    expect(formatSeconds(14400, locale).raw).toBe("14400");
    expect(formatUtilization(0.625, locale)).toEqual({
      display: new Intl.NumberFormat(locale, {
        style: "percent",
        maximumFractionDigits: 2,
      }).format(0.625),
      raw: "0.625",
    });
  });

  it("rejects non-finite values rather than formatting invented output", () => {
    expect(() => formatNumber(Number.NaN, "zh-CN")).toThrow(TypeError);
  });
});
