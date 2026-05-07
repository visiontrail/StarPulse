import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["selector", "[data-theme='dark']"],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "rgb(var(--color-canvas) / <alpha-value>)",
        paper: "rgb(var(--color-paper) / <alpha-value>)",
        surface: "rgb(var(--color-surface) / <alpha-value>)",
        "surface-soft": "rgb(var(--color-surface-soft) / <alpha-value>)",
        ink: "rgb(var(--color-ink) / <alpha-value>)",
        muted: "rgb(var(--color-muted) / <alpha-value>)",
        accent: "rgb(var(--color-accent) / <alpha-value>)",
        ok: "rgb(var(--color-ok) / <alpha-value>)",
        warn: "rgb(var(--color-warn) / <alpha-value>)",
        error: "rgb(var(--color-error) / <alpha-value>)",
        info: "rgb(var(--color-info) / <alpha-value>)"
      },
      borderColor: {
        warm: "rgb(var(--border-warm))",
        "warm-strong": "rgb(var(--border-warm-strong))"
      },
      borderRadius: {
        DEFAULT: "8px"
      },
      fontFamily: {
        sans: ["var(--font-ui)", "Avenir Next", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "Berkeley Mono", "SFMono-Regular", "Menlo", "monospace"]
      },
      boxShadow: {
        panel: "0 1px 0 oklab(0.263084 -0.00230259 0.0124794 / 0.06)"
      }
    }
  },
  plugins: []
};

export default config;
