import enUS from "antd/locale/en_US";
import zhCN from "antd/locale/zh_CN";
import {
  createContext,
  createElement,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";

import { enUSMessages, type TranslationKey } from "./dictionaries/en-US";
import { zhCNMessages } from "./dictionaries/zh-CN";
import {
  defaultLocale,
  fallbackLocale,
  isAppLocale,
  localePreferenceKey,
  terminologyVersion,
  type AppLocale,
  type MessageValues,
} from "./types";

const dictionaries = {
  "en-US": enUSMessages,
  "zh-CN": zhCNMessages,
} as const;

const antDesignLocales = {
  "en-US": enUS,
  "zh-CN": zhCN,
} as const;

function interpolate(message: string, values: MessageValues | undefined): string {
  if (values === undefined) return message;
  return message.replace(/\{([A-Za-z][A-Za-z0-9_]*)\}/gu, (token, name: string) =>
    Object.hasOwn(values, name) ? String(values[name]) : token,
  );
}

export function translate(
  locale: AppLocale,
  key: TranslationKey,
  values?: MessageValues,
): string {
  return interpolate(dictionaries[locale][key], values);
}

function storedLocale(): AppLocale {
  try {
    const value = globalThis.localStorage?.getItem(localePreferenceKey);
    return isAppLocale(value) ? value : defaultLocale;
  } catch {
    return defaultLocale;
  }
}

export interface LocaleContextValue {
  readonly locale: AppLocale;
  readonly terminologyVersion: typeof terminologyVersion;
  readonly antDesignLocale: (typeof antDesignLocales)[AppLocale];
  readonly t: (key: TranslationKey, values?: MessageValues) => string;
  readonly setLocale: (locale: AppLocale) => void;
}

const fallbackContext: LocaleContextValue = {
  locale: fallbackLocale,
  terminologyVersion,
  antDesignLocale: antDesignLocales[fallbackLocale],
  t: (key, values) => translate(fallbackLocale, key, values),
  setLocale: () => undefined,
};

const LocaleContext = createContext<LocaleContextValue>(fallbackContext);

export function LocaleProvider({
  children,
  initialLocale,
}: PropsWithChildren<{ initialLocale?: AppLocale }>) {
  const [locale, setLocaleState] = useState<AppLocale>(() => initialLocale ?? storedLocale());
  const setLocale = useCallback((next: AppLocale) => {
    setLocaleState(next);
    try {
      globalThis.localStorage?.setItem(localePreferenceKey, next);
    } catch {
      // A blocked browser storage area must not block localization.
    }
  }, []);
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);
  const value = useMemo<LocaleContextValue>(
    () => ({
      locale,
      terminologyVersion,
      antDesignLocale: antDesignLocales[locale],
      t: (key, values) => translate(locale, key, values),
      setLocale,
    }),
    [locale, setLocale],
  );
  return createElement(LocaleContext.Provider, { value }, children);
}

export function useLocale(): LocaleContextValue {
  return useContext(LocaleContext);
}

export { localePreferenceKey } from "./types";
