"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState
} from "react";

import en, { type Dict } from "./locales/en";
import zh from "./locales/zh";
import es from "./locales/es";
import fr from "./locales/fr";
import de from "./locales/de";
import ja from "./locales/ja";

export const SUPPORTED_LOCALES = ["zh", "en", "es", "fr", "de", "ja"] as const;
export type Locale = (typeof SUPPORTED_LOCALES)[number];

const dictionaries: Record<Locale, Dict> = { zh, en, es, fr, de, ja };

const STORAGE_KEY = "starpulse.locale";
const DEFAULT_LOCALE: Locale = "zh";

export type TranslateFn = (
  key: keyof Dict | (string & {}),
  params?: Record<string, string | number>
) => string;

type LocaleContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: TranslateFn;
};

const LocaleContext = createContext<LocaleContextValue | null>(null);

function detectFromNavigator(): Locale | null {
  if (typeof navigator === "undefined") return null;
  const candidates = [navigator.language, ...(navigator.languages ?? [])];
  for (const raw of candidates) {
    const code = (raw ?? "").toLowerCase();
    if (!code) continue;
    if (code.startsWith("zh")) return "zh";
    if (code.startsWith("en")) return "en";
    if (code.startsWith("es")) return "es";
    if (code.startsWith("fr")) return "fr";
    if (code.startsWith("de")) return "de";
    if (code.startsWith("ja")) return "ja";
  }
  return null;
}

function format(template: string, params?: Record<string, string | number>) {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (_, name) => {
    const value = params[name];
    return value === undefined ? `{${name}}` : String(value);
  });
}

export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored && (SUPPORTED_LOCALES as readonly string[]).includes(stored)) {
      setLocaleState(stored as Locale);
      return;
    }
    const detected = detectFromNavigator();
    if (detected) setLocaleState(detected);
  }, []);

  useEffect(() => {
    if (typeof document !== "undefined") {
      document.documentElement.setAttribute("lang", locale);
    }
  }, [locale]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, next);
    }
  }, []);

  const t = useCallback<TranslateFn>(
    (key, params) => {
      const dict = dictionaries[locale];
      const fallback = dictionaries.en;
      const template =
        (dict as Record<string, string>)[key as string] ??
        (fallback as Record<string, string>)[key as string] ??
        (key as string);
      return format(template, params);
    },
    [locale]
  );

  const value = useMemo(() => ({ locale, setLocale, t }), [locale, setLocale, t]);

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale() {
  const ctx = useContext(LocaleContext);
  if (!ctx) throw new Error("useLocale must be used inside LocaleProvider");
  return ctx;
}

export function useT(): TranslateFn {
  return useLocale().t;
}

export function localizeStatus(t: TranslateFn, status: string | null | undefined): string {
  if (!status) return t("common.dash");
  const key = `status.${status}`;
  const translated = t(key);
  return translated === key ? status.replaceAll("_", " ") : translated;
}
