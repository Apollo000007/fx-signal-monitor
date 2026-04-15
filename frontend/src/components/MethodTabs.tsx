"use client";

import { Brain, Layers, LineChart, Sparkles, Trophy } from "lucide-react";
import { cn } from "@/lib/utils";
import { useSignalsStore } from "@/store/signals";
import type { Method } from "@/lib/types";

interface TabDef {
  key: Method;
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  /** active 時のグラデーションカラー。 */
  accent: string;
  /** タブ強調レベル (3手法合意は最高ランク) */
  rank?: "base" | "combo" | "ultimate";
}

const TABS: TabDef[] = [
  {
    key: "orz",
    title: "ORZ 手法",
    subtitle: "Dow + SMA + 一目雲",
    icon: <LineChart className="h-4 w-4" />,
    accent: "from-accent-cyan/60 to-accent-cyan/10 border-accent-cyan/40 text-accent-cyan",
  },
  {
    key: "pdhl",
    title: "PDH/PDL 手法",
    subtitle: "ブレイク→リテスト→フラッグ",
    icon: <Sparkles className="h-4 w-4" />,
    accent: "from-accent-amber/60 to-accent-amber/10 border-accent-amber/40 text-accent-amber",
  },
  {
    key: "both",
    title: "ORZ + PDHL 合意",
    subtitle: "既存 2 手法が同方向",
    icon: <Layers className="h-4 w-4" />,
    accent: "from-accent-purple/60 to-accent-purple/10 border-accent-purple/40 text-accent-purple",
    rank: "combo",
  },
  {
    key: "claude",
    title: "Claude Confluence",
    subtitle: "MTF + ATR収縮 + Donchian",
    icon: <Brain className="h-4 w-4" />,
    accent: "from-accent-green/60 to-accent-green/10 border-accent-green/40 text-accent-green",
  },
  {
    key: "triple",
    title: "3 手法合意 🏆",
    subtitle: "ORZ + PDHL + Claude 全一致",
    icon: <Trophy className="h-4 w-4" />,
    accent:
      "from-accent-amber/70 via-accent-red/40 to-accent-purple/40 border-accent-amber/60 text-accent-amber",
    rank: "ultimate",
  },
];

export function MethodTabs() {
  const { method, setMethod, records } = useSignalsStore();

  // タブごとのアラート件数バッジ
  const alertCounts: Record<Method, number> = {
    orz: 0,
    pdhl: 0,
    both: 0,
    claude: 0,
    triple: 0,
  };
  for (const r of records) {
    if (r.orz.is_alert) alertCounts.orz += 1;
    if (r.pdhl.is_alert) alertCounts.pdhl += 1;
    if (r.both.is_alert) alertCounts.both += 1;
    if (r.claude?.is_alert) alertCounts.claude += 1;
    if (r.triple?.is_alert) alertCounts.triple += 1;
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-2.5">
      {TABS.map((t) => {
        const active = method === t.key;
        const count = alertCounts[t.key];
        return (
          <button
            key={t.key}
            onClick={() => setMethod(t.key)}
            className={cn(
              "relative overflow-hidden rounded-2xl border p-3 text-left transition",
              "flex items-start gap-2.5 min-h-[76px]",
              active
                ? cn("bg-gradient-to-br", t.accent, "shadow-glow")
                : "border-border/60 bg-bg-soft/40 text-text-dim hover:text-text hover:border-border",
              t.rank === "ultimate" && !active && "border-accent-amber/25",
            )}
          >
            <div
              className={cn(
                "rounded-lg p-2 shrink-0",
                active ? "bg-bg-card/60" : "bg-bg-card/40",
              )}
            >
              {t.icon}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="text-[13px] font-semibold tracking-tight leading-tight">
                  {t.title}
                </span>
                {count > 0 && (
                  <span
                    className={cn(
                      "px-1.5 py-0.5 rounded-full text-[10px] font-bold font-mono",
                      active
                        ? "bg-bg-card/80"
                        : t.rank === "ultimate"
                          ? "bg-accent-amber/25 text-accent-amber"
                          : "bg-accent-amber/20 text-accent-amber",
                    )}
                  >
                    {count}
                  </span>
                )}
              </div>
              <div className="text-[10px] opacity-70 mt-0.5 truncate">{t.subtitle}</div>
            </div>
            {active && <div className="absolute inset-x-0 bottom-0 h-0.5 bg-accent-gradient" />}
          </button>
        );
      })}
    </div>
  );
}
