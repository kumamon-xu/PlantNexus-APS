export const supportedLocales = ["zh-CN", "en-US"] as const;

export type AppLocale = (typeof supportedLocales)[number];

export const defaultLocale: AppLocale = "zh-CN";
export const fallbackLocale: AppLocale = "en-US";
export const localePreferenceKey = "plantnexus.locale.v1";
export const terminologyVersion = "official-zh-cn-terminology.v1";

export type MessageValues = Readonly<Record<string, string | number>>;

export interface LocalizedMachineValue {
  readonly known: boolean;
  readonly label: string;
  readonly raw: string;
}

export interface FormattedRawValue {
  readonly display: string;
  readonly raw: string;
}

export function isAppLocale(value: unknown): value is AppLocale {
  return supportedLocales.some((locale) => locale === value);
}
