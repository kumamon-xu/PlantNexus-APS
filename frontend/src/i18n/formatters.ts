import type { AppLocale, FormattedRawValue } from "./types";

function finite(value: number): number {
  if (!Number.isFinite(value)) throw new TypeError("localized numeric value must be finite");
  return value;
}

export function formatNumber(
  value: number,
  locale: AppLocale,
  options: Intl.NumberFormatOptions = {},
): FormattedRawValue {
  return {
    display: new Intl.NumberFormat(locale, options).format(finite(value)),
    raw: String(value),
  };
}

export function formatInteger(value: number, locale: AppLocale): FormattedRawValue {
  return formatNumber(value, locale, { maximumFractionDigits: 0 });
}

export function formatSeconds(value: number, locale: AppLocale): FormattedRawValue {
  const formatted = formatInteger(value, locale);
  return {
    display: locale === "zh-CN" ? `${formatted.display} 秒` : `${formatted.display} seconds`,
    raw: formatted.raw,
  };
}

export function formatUtilization(value: number, locale: AppLocale): FormattedRawValue {
  return {
    display: new Intl.NumberFormat(locale, {
      style: "percent",
      maximumFractionDigits: 2,
    }).format(finite(value)),
    raw: String(value),
  };
}

export function formatUtc(value: string, locale: AppLocale): FormattedRawValue {
  const epoch = Date.parse(value);
  if (Number.isNaN(epoch) || !value.endsWith("Z")) {
    return {
      display: locale === "zh-CN" ? `未知（${value}）` : `Unknown (${value})`,
      raw: value,
    };
  }
  return {
    display: new Intl.DateTimeFormat(locale, {
      dateStyle: "medium",
      timeStyle: "medium",
      timeZone: "UTC",
    }).format(epoch),
    raw: value,
  };
}
