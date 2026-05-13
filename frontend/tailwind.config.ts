import type { Config } from "tailwindcss";

const colorVar = (name: string) => `rgb(var(${name}) / <alpha-value>)`;

const config: Config = {
  darkMode: "class",
  content: [
    "./src/app/**/*.{ts,tsx}",
    "./src/components/**/*.{ts,tsx}",
    "./src/lib/**/*.{ts,tsx}",
  ],
  safelist: [
    // スコアゲージで動的に組み立てる gradient クラス
    { pattern: /^(from|via|to)-(emerald|cyan|sky|amber|lime|fuchsia|violet|rose|orange|yellow|indigo)-(300|400|500|600)$/ },
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: colorVar("--color-bg"),
          soft: colorVar("--color-bg-soft"),
          card: colorVar("--color-bg-card"),
          hover: colorVar("--color-bg-hover"),
        },
        border: {
          DEFAULT: colorVar("--color-border"),
          soft: colorVar("--color-border-soft"),
        },
        text: {
          DEFAULT: colorVar("--color-text"),
          dim: colorVar("--color-text-dim"),
          faint: colorVar("--color-text-faint"),
        },
        accent: {
          gold: colorVar("--color-accent-gold"),
          amber: colorVar("--color-accent-amber"),
          ivory: colorVar("--color-accent-ivory"),
          violet: colorVar("--color-accent-violet"),
          indigo: colorVar("--color-accent-indigo"),
          cyan: colorVar("--color-accent-cyan"),
          green: colorVar("--color-accent-green"),
          red: colorVar("--color-accent-red"),
          purple: colorVar("--color-accent-purple"),
        },
      },
      fontFamily: {
        serif: [
          "var(--font-display)",
          "'Noto Serif JP'",
          "Georgia",
          "serif",
        ],
        sans: [
          "var(--font-sans)",
          "sans-serif",
        ],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "'JetBrains Mono'", "Menlo", "monospace"],
      },
      boxShadow: {
        glow: "var(--shadow-glow)",
        card: "var(--shadow-card)",
        halo: "var(--shadow-halo)",
        oracle: "var(--shadow-oracle)",
      },
      backgroundImage: {
        "grid-fade": "var(--bg-grid-fade)",
        "accent-gradient": "var(--bg-accent-gradient)",
        "aura-gradient": "var(--bg-aura-gradient)",
        "marble": "var(--bg-marble)",
      },
      animation: {
        "fade-in": "fadeIn 0.4s ease-out",
        "slide-up": "slideUp 0.4s ease-out",
        "pulse-soft": "pulseSoft 2s ease-in-out infinite",
        shimmer: "shimmer 2s linear infinite",
        "halo-spin": "haloSpin 18s linear infinite",
        "aura-breathe": "auraBreathe 6s ease-in-out infinite",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        pulseSoft: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.6" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        haloSpin: {
          "0%": { transform: "rotate(0deg)" },
          "100%": { transform: "rotate(360deg)" },
        },
        auraBreathe: {
          "0%, 100%": { opacity: "0.55", transform: "scale(1)" },
          "50%": { opacity: "0.85", transform: "scale(1.03)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
