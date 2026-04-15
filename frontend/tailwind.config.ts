import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./src/app/**/*.{ts,tsx}",
    "./src/components/**/*.{ts,tsx}",
    "./src/lib/**/*.{ts,tsx}",
  ],
  safelist: [
    // スコアゲージで動的に組み立てる gradient クラス
    { pattern: /^(from|via|to)-(emerald|cyan|sky|amber|lime|fuchsia|violet|rose|orange)-(300|400|500|600)$/ },
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: "#0a0e1a",
          soft: "#0f1526",
          card: "#121932",
          hover: "#1a2342",
        },
        border: {
          DEFAULT: "#1f2a48",
          soft: "#182240",
        },
        text: {
          DEFAULT: "#e7ecf7",
          dim: "#8a95b3",
          faint: "#4d5878",
        },
        accent: {
          cyan: "#22d3ee",
          purple: "#a855f7",
          green: "#10b981",
          red: "#f43f5e",
          amber: "#f59e0b",
        },
      },
      fontFamily: {
        sans: [
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "'Segoe UI'",
          "'Hiragino Sans'",
          "'Noto Sans JP'",
          "'Yu Gothic UI'",
          "Meiryo",
          "sans-serif",
        ],
        mono: ["ui-monospace", "SFMono-Regular", "'JetBrains Mono'", "Menlo", "monospace"],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(168,85,247,0.25), 0 10px 40px -10px rgba(168,85,247,0.35)",
        card: "0 4px 24px -8px rgba(0,0,0,0.5), inset 0 0 0 1px rgba(255,255,255,0.03)",
      },
      backgroundImage: {
        "grid-fade":
          "radial-gradient(ellipse at top, rgba(34,211,238,0.08), transparent 60%), radial-gradient(ellipse at bottom, rgba(168,85,247,0.08), transparent 60%)",
        "accent-gradient":
          "linear-gradient(135deg, #22d3ee 0%, #a855f7 100%)",
      },
      animation: {
        "fade-in": "fadeIn 0.4s ease-out",
        "slide-up": "slideUp 0.4s ease-out",
        "pulse-soft": "pulseSoft 2s ease-in-out infinite",
        shimmer: "shimmer 2s linear infinite",
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
      },
    },
  },
  plugins: [],
};

export default config;
