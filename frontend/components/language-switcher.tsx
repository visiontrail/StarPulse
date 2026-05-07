"use client";

import * as Select from "@radix-ui/react-select";
import { Check, ChevronDown, Languages } from "lucide-react";

import { SUPPORTED_LOCALES, useLocale, type Locale } from "@/lib/i18n";

const LABEL_KEYS: Record<Locale, string> = {
  zh: "lang.zh",
  en: "lang.en",
  es: "lang.es",
  fr: "lang.fr",
  de: "lang.de",
  ja: "lang.ja"
};

export function LanguageSwitcher() {
  const { locale, setLocale, t } = useLocale();

  return (
    <Select.Root value={locale} onValueChange={(value) => setLocale(value as Locale)}>
      <Select.Trigger
        aria-label={t("lang.label")}
        title={t("lang.label")}
        className="inline-flex h-8 items-center gap-1.5 rounded border border-warm bg-paper px-2 text-xs text-ink outline-none transition hover:border-warm-strong"
      >
        <Languages className="h-3.5 w-3.5" aria-hidden />
        <Select.Value />
        <Select.Icon>
          <ChevronDown className="h-3.5 w-3.5" />
        </Select.Icon>
      </Select.Trigger>
      <Select.Portal>
        <Select.Content
          position="popper"
          sideOffset={4}
          className="z-50 overflow-hidden rounded border border-warm bg-paper shadow-lg"
        >
          <Select.Viewport className="p-1">
            {SUPPORTED_LOCALES.map((value) => (
              <Select.Item
                key={value}
                value={value}
                className="relative flex h-8 cursor-default select-none items-center rounded px-8 text-sm text-ink outline-none data-[highlighted]:bg-surface"
              >
                <Select.ItemIndicator className="absolute left-2">
                  <Check className="h-4 w-4" />
                </Select.ItemIndicator>
                <Select.ItemText>{t(LABEL_KEYS[value])}</Select.ItemText>
              </Select.Item>
            ))}
          </Select.Viewport>
        </Select.Content>
      </Select.Portal>
    </Select.Root>
  );
}
