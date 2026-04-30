import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#f2f1ed",
        paper: "#f7f7f4",
        surface: "#e6e5e0",
        "surface-soft": "#ebeae5",
        ink: "#26251e",
        muted: "#6f6b60",
        accent: "#f54e00",
        ok: "#1f8a65",
        warn: "#c08532",
        error: "#cf2d56",
        info: "#426a9b"
      },
      borderColor: {
        warm: "oklab(0.263084 -0.00230259 0.0124794 / 0.14)",
        "warm-strong": "oklab(0.263084 -0.00230259 0.0124794 / 0.26)"
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
