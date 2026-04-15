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
    { pattern: /^(from|via|to)-(emerald|cyan|sky|amber|lime|fuchsia|violet|rose|orange|yellow|indigo)-(300|400|500|600)$/ },
  ],
  theme: {
    extend: {
      colors: {
        // --- Olympus × Enlightenment palette ---
        // Base = 夜のオリンポス (deep indigo / obsidian) + 紫 aura
        bg: {
          DEFAULT: "#0b0a1f",       // 夜空・冥界の黒紫
          soft: "#14122e",          // 月光に染まる神殿の影
          card: "#1a1636",          // 大理石の奥行き
          hover: "#241d4a",         // 瞑想のヴェール
        },
        border: {
          DEFAULT: "#3a2e5e",       // 紫水晶
          soft: "#2a2247",
        },
        text: {
          DEFAULT: "#f5ecd7",       // 神託の象牙 (ivory)
          dim: "#c9b88a",           // 古代金のエコー
          faint: "#7a6b9a",         // 紫霞
        },
        accent: {
          // --- 神々の輝き ---
          gold: "#e9c46a",          // Apollon / 黄金律
          amber: "#f0a93b",         // 聖火
          ivory: "#f8eed1",         // 神殿の大理石
          violet: "#a855f7",        // 第七チャクラ / 悟り
          indigo: "#6d5dfc",        // 第六チャクラ / 直観
          cyan: "#5ecbd6",          // エーテル
          green: "#4ade80",         // Gaia / 生命
          red: "#e25c73",           // Ares / 警告
          purple: "#a855f7",        // 後方互換
        },
      },
      fontFamily: {
        // 見出し = 古代のセリフ、本文 = 可読性重視のサンセリフ、数値 = モノ
        serif: [
          "'Cormorant Garamond'",
          "'EB Garamond'",
          "'Cinzel'",
          "'Noto Serif JP'",
          "Georgia",
          "serif",
        ],
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
        glow: "0 0 0 1px rgba(233,196,106,0.28), 0 10px 40px -10px rgba(233,196,106,0.35)",
        card: "0 4px 28px -10px rgba(0,0,0,0.6), inset 0 0 0 1px rgba(245,236,215,0.04)",
        halo: "0 0 40px -8px rgba(168,85,247,0.45), 0 0 80px -20px rgba(233,196,106,0.25)",
        oracle: "inset 0 1px 0 0 rgba(248,238,209,0.08), 0 8px 32px -12px rgba(109,93,252,0.35)",
      },
      backgroundImage: {
        "grid-fade":
          "radial-gradient(ellipse at top, rgba(168,85,247,0.12), transparent 60%), radial-gradient(ellipse at bottom, rgba(233,196,106,0.08), transparent 60%)",
        // 金 → 紫 のオリンポスグラデーション
        "accent-gradient":
          "linear-gradient(135deg, #e9c46a 0%, #f0a93b 35%, #a855f7 100%)",
        "aura-gradient":
          "conic-gradient(from 180deg at 50% 50%, rgba(233,196,106,0.18), rgba(168,85,247,0.18), rgba(94,203,214,0.15), rgba(233,196,106,0.18))",
        "marble":
          "radial-gradient(ellipse at 20% 10%, rgba(248,238,209,0.06), transparent 55%), radial-gradient(ellipse at 80% 90%, rgba(168,85,247,0.08), transparent 55%)",
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
