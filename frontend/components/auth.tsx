"use client";

import { ChevronDown, Check, LogIn, LogOut, Monitor, Moon, Sun, User } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useSession } from "@/lib/session";
import { BrandMark } from "@/components/brand";
import { NeuralLoginField } from "@/components/neural-login-field";
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
  const { locale, setLocale } = useLocale();
  const { login } = useSession();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [localeOpen, setLocaleOpen] = useState(false);
  const localeContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!localeOpen) return;
    function onMouseDown(e: MouseEvent) {
      if (localeContainerRef.current && !localeContainerRef.current.contains(e.target as Node)) {
        setLocaleOpen(false);
      }
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setLocaleOpen(false);
    }
    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [localeOpen]);

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
    <div
      data-theme="dark"
      className="relative isolate min-h-screen overflow-hidden bg-black text-white"
    >
      <NeuralLoginField />

      <div className="pointer-events-none absolute inset-0 z-10 border border-white/10" />
      <div className="relative z-20 flex min-h-screen min-h-dvh items-center justify-center px-4 py-8 sm:px-6 lg:justify-end lg:px-12 xl:px-20">
        <div className="absolute left-4 top-4 sm:left-6 sm:top-6">
          <BrandMark className="h-9 w-[178px] sm:h-10 sm:w-[198px]" />
        </div>

        <div className="w-full max-w-[392px] border border-transparent bg-[linear-gradient(to_top,rgb(9,9,11),rgba(9,9,11,0.62),rgba(0,0,0,0))] p-px shadow-[0_24px_80px_rgba(0,0,0,0.42)]">
          <div className="bg-black/72 px-5 py-6 backdrop-blur-xl sm:px-6">
            <div className="mb-6 grid gap-4">
              <div className="h-px w-full bg-gradient-to-r from-transparent via-white/35 to-transparent" />
              <div>
                <p className="mb-2 font-mono text-[11px] uppercase tracking-[0.18em] text-accent/80">
                  Galaxy Space - Star Pulse
                </p>
                <h1 className="text-3xl font-semibold leading-none tracking-normal text-white sm:text-[40px]">
                  {t("auth.signIn")}
                </h1>
              </div>
              <div className="grid grid-cols-[1fr_40px_1fr] items-center gap-3">
                <div className="h-px bg-white/18" />
                <div className="h-1 border-x border-accent/70" />
                <div className="h-px bg-white/18" />
              </div>
            </div>

            <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
              <div>
                <label className="mb-1.5 block font-mono text-[11px] uppercase text-zinc-400">
                  {t("auth.username")}
                </label>
                <input
                  type="text"
                  autoComplete="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  className="h-11 w-full rounded-none border border-white/12 bg-white/[0.055] px-3 text-sm text-white caret-accent outline-none transition placeholder:text-zinc-600 focus:border-accent/70 focus:bg-white/[0.08] focus:ring-1 focus:ring-accent/25"
                />
              </div>
              <div>
                <label className="mb-1.5 block font-mono text-[11px] uppercase text-zinc-400">
                  {t("auth.password")}
                </label>
                <input
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="h-11 w-full rounded-none border border-white/12 bg-white/[0.055] px-3 text-sm text-white caret-accent outline-none transition placeholder:text-zinc-600 focus:border-accent/70 focus:bg-white/[0.08] focus:ring-1 focus:ring-accent/25"
                />
              </div>
              {error ? (
                <p className="border border-error/30 bg-error/10 px-3 py-2 text-sm text-error">
                  {error}
                </p>
              ) : null}
              <button
                type="submit"
                disabled={loading}
                className="group inline-flex h-11 w-full items-center justify-center gap-2 rounded-none border border-white bg-white px-3 text-sm font-semibold text-black transition duration-200 hover:border-accent hover:bg-accent disabled:cursor-not-allowed disabled:opacity-55"
              >
                <LogIn
                  className={cn("h-4 w-4 transition", loading && "animate-pulse")}
                  aria-hidden="true"
                />
                {t("auth.signIn")}
              </button>
            </form>

          </div>
        </div>
      </div>
      <div ref={localeContainerRef} className="absolute bottom-4 right-4 z-30 sm:bottom-6 sm:right-6">
        <button
          type="button"
          onClick={() => setLocaleOpen((v) => !v)}
          aria-haspopup="menu"
          aria-expanded={localeOpen}
          className={cn(
            "inline-flex h-9 items-center gap-1.5 border border-white/20 bg-black/55 px-2.5 text-xs text-zinc-100 backdrop-blur-md transition hover:border-white/35",
            localeOpen && "border-accent/70 text-accent"
          )}
        >
          <span>{t("lang.label")}</span>
          <ChevronDown className={cn("h-3.5 w-3.5 transition", localeOpen && "rotate-180")} aria-hidden="true" />
        </button>

        {localeOpen ? (
          <div
            role="menu"
            className="absolute bottom-full right-0 mb-2 grid w-44 gap-1 border border-white/20 bg-black/78 p-1.5 backdrop-blur-xl"
          >
            {SUPPORTED_LOCALES.map((value) => {
              const active = locale === value;
              return (
                <button
                  key={value}
                  type="button"
                  onClick={() => {
                    setLocale(value);
                    setLocaleOpen(false);
                  }}
                  aria-pressed={active}
                  className={cn(
                    "inline-flex h-8 items-center justify-between gap-1 border px-2 text-xs transition",
                    active
                      ? "border-accent/70 bg-accent/15 text-accent"
                      : "border-white/10 bg-white/[0.04] text-zinc-100 hover:border-white/35"
                  )}
                >
                  <span className="truncate">{t(LOCALE_LABEL_KEYS[value])}</span>
                  {active ? <Check className="h-3.5 w-3.5 shrink-0" aria-hidden="true" /> : null}
                </button>
              );
            })}
          </div>
        ) : null}
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
