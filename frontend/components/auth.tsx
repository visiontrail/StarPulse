"use client";

import { ChevronDown, Check, LogIn, LogOut, Monitor, Moon, Sun, User } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useSession } from "@/lib/session";
import { BrandMark } from "@/components/brand";
import { Button } from "@/components/ui";
import { useT } from "@/lib/i18n";
import { SUPPORTED_LOCALES, useLocale, type Locale } from "@/lib/i18n";
import {
  THEME_PREFERENCES,
  useTheme,
  type ThemePreference
} from "@/lib/theme";
import { cn } from "@/lib/utils";

// ── Login View ─────────────────────────────────────────────────────────────

export function LoginView() {
  const t = useT();
  const { login } = useSession();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(username, password);
    } catch {
      setError(t("auth.invalid"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-sm rounded border border-warm bg-canvas/95 p-6 shadow-sm">
        <div className="mb-6 space-y-4">
          <BrandMark className="h-11 w-[218px]" />
          <div>
            <h1 className="text-lg font-semibold">{t("auth.signIn")}</h1>
          </div>
        </div>

        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
          <div>
            <label className="mb-1 block font-mono text-[11px] uppercase text-muted">
              {t("auth.username")}
            </label>
            <input
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              className="w-full rounded border border-warm bg-paper px-3 py-2 text-sm text-ink focus:outline-none focus:ring-1 focus:ring-accent/50"
            />
          </div>
          <div>
            <label className="mb-1 block font-mono text-[11px] uppercase text-muted">
              {t("auth.password")}
            </label>
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full rounded border border-warm bg-paper px-3 py-2 text-sm text-ink focus:outline-none focus:ring-1 focus:ring-accent/50"
            />
          </div>
          {error ? (
            <p className="text-sm text-error">{error}</p>
          ) : null}
          <Button type="submit" busy={loading} className="w-full justify-center">
            <LogIn className="h-4 w-4" aria-hidden="true" />
            {t("auth.signIn")}
          </Button>
        </form>
      </div>
    </div>
  );
}

// ── Session Header ─────────────────────────────────────────────────────────

const LOCALE_LABEL_KEYS: Record<Locale, string> = {
  zh: "lang.zh",
  en: "lang.en",
  es: "lang.es",
  fr: "lang.fr",
  de: "lang.de",
  ja: "lang.ja"
};

const THEME_ICONS: Record<ThemePreference, React.ReactNode> = {
  light: <Sun className="h-3.5 w-3.5" aria-hidden="true" />,
  dark: <Moon className="h-3.5 w-3.5" aria-hidden="true" />,
  system: <Monitor className="h-3.5 w-3.5" aria-hidden="true" />
};

export function SessionHeader() {
  const t = useT();
  const { user, logout } = useSession();
  const { locale, setLocale } = useLocale();
  const { preference, setPreference } = useTheme();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onMouseDown(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  if (!user) return null;

  async function handleLogout() {
    setBusy(true);
    try {
      await logout();
    } finally {
      setBusy(false);
      setOpen(false);
    }
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        title={t("user.menu")}
        className={cn(
          "inline-flex h-8 items-center gap-1.5 rounded border border-warm bg-paper px-2 text-xs text-ink transition hover:border-warm-strong",
          open && "border-warm-strong"
        )}
      >
        <User className="h-3.5 w-3.5" aria-hidden="true" />
        <span className="font-medium">{user.display_name}</span>
        <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />
      </button>

      {open ? (
        <div
          role="menu"
          className="absolute right-0 top-full z-50 mt-2 w-72 overflow-hidden rounded border border-warm bg-paper shadow-lg"
        >
          <div className="border-b border-warm px-3 py-2.5">
            <p className="text-sm font-semibold text-ink">{user.display_name}</p>
            <p className="mt-0.5 text-xs text-muted">
              {user.roles.length > 0 ? user.roles.join(", ") : t("auth.noRole")}
            </p>
          </div>

          <div className="border-b border-warm px-3 py-2.5">
            <p className="mb-1.5 font-mono text-[11px] uppercase text-muted">
              {t("theme.label")}
            </p>
            <div className="grid grid-cols-3 gap-1">
              {THEME_PREFERENCES.map((value) => {
                const active = preference === value;
                return (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setPreference(value)}
                    aria-pressed={active}
                    className={cn(
                      "inline-flex h-8 items-center justify-center gap-1 rounded border text-xs transition",
                      active
                        ? "border-accent/60 bg-accent/10 text-accent"
                        : "border-warm bg-canvas text-ink hover:border-warm-strong"
                    )}
                  >
                    {THEME_ICONS[value]}
                    <span>{t(`theme.${value}`)}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="border-b border-warm px-3 py-2.5">
            <p className="mb-1.5 font-mono text-[11px] uppercase text-muted">
              {t("lang.label")}
            </p>
            <div className="grid grid-cols-2 gap-1">
              {SUPPORTED_LOCALES.map((value) => {
                const active = locale === value;
                return (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setLocale(value)}
                    aria-pressed={active}
                    className={cn(
                      "inline-flex h-8 items-center justify-between gap-1 rounded border px-2 text-xs transition",
                      active
                        ? "border-accent/60 bg-accent/10 text-accent"
                        : "border-warm bg-canvas text-ink hover:border-warm-strong"
                    )}
                  >
                    <span className="truncate">{t(LOCALE_LABEL_KEYS[value])}</span>
                    {active ? <Check className="h-3.5 w-3.5 shrink-0" aria-hidden="true" /> : null}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="p-2">
            <button
              type="button"
              onClick={() => void handleLogout()}
              disabled={busy}
              className="inline-flex h-8 w-full items-center justify-center gap-2 rounded border border-warm bg-canvas px-2 text-xs text-ink transition hover:border-error/40 hover:text-error disabled:cursor-not-allowed disabled:opacity-50"
            >
              <LogOut className="h-3.5 w-3.5" aria-hidden="true" />
              <span>{t("auth.signOut")}</span>
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
