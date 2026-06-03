"use client";

import { Flame, Eye, Sun, TrendingUp, CandlestickChart } from "lucide-react";
import { cn } from "@/lib/utils";
import { useSignalsStore } from "@/store/signals";
import type { Method } from "@/lib/types";
import { isEvaTheme } from "@/lib/visualTheme";

interface TabDef {
  key: Method;
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  /** active 時のグラデーションカラー。 */
  accent: string;
  /** タブ強調レベル (3手法合意は最高ランク) */
  rank?: "base" | "combo" | "ultimate";
  /** +EV 検証で降格 (アラート対象外・参考表示のみ) */
  reference?: boolean;
}

const OLYMPUS_TABS: TabDef[] = [
  {
    key: "orz",
    title: "Athena · ORZ",
    subtitle: "Dow + SMA + 一目雲 — 参考",
    icon: <Eye className="h-4 w-4" />,
    accent: "from-accent-cyan/60 to-accent-cyan/10 border-accent-cyan/40 text-accent-cyan",
    reference: true,
  },
  {
    key: "pdhl",
    title: "Hermes · PDH/PDL",
    subtitle: "ブレイク → リテスト — 参考",
    icon: <Flame className="h-4 w-4" />,
    accent: "from-accent-gold/60 to-accent-gold/10 border-accent-gold/40 text-accent-gold",
    reference: true,
  },
  {
    key: "triple",
    title: "Zeus · 三位合一 ☀",
    subtitle: "ORZ + PDHL + Claude 全合意",
    icon: <Sun className="h-4 w-4" />,
    accent:
      "from-accent-gold/80 via-accent-amber/50 to-accent-violet/60 border-accent-gold/70 text-accent-gold",
    rank: "ultimate",
  },
  {
    key: "dtp",
    title: "Nike · DTP 押し目",
    subtitle: "日足トレンド押し目 — 勝利の女神",
    icon: <TrendingUp className="h-4 w-4" />,
    accent:
      "from-accent-green/70 via-accent-cyan/40 to-accent-gold/50 border-accent-green/60 text-accent-green",
    rank: "ultimate",
  },
  {
    key: "pa",
    title: "Apollo · PA パターン",
    subtitle: "ローソク足型 + 上位足 + 節目 — 予言",
    icon: <CandlestickChart className="h-4 w-4" />,
    accent:
      "from-accent-violet/70 via-accent-cyan/40 to-accent-gold/50 border-accent-violet/60 text-accent-violet",
    rank: "ultimate",
  },
];

const EVA_TABS: TabDef[] = [
  {
    key: "orz",
    title: "OPS-01 · ORZ",
    subtitle: "DOW / SMA / ICHIMOKU (REF)",
    icon: <Eye className="h-4 w-4" />,
    accent: "from-accent-cyan/35 to-bg-card border-accent-cyan/60 text-accent-cyan",
    reference: true,
  },
  {
    key: "pdhl",
    title: "OPS-02 · PDH/PDL",
    subtitle: "BREAK / RETEST (REF)",
    icon: <Flame className="h-4 w-4" />,
    accent: "from-accent-red/40 to-bg-card border-accent-red/70 text-accent-red",
    reference: true,
  },
  {
    key: "triple",
    title: "FINAL-05 · 三手法",
    subtitle: "FULL CONFLUENCE",
    icon: <Sun className="h-4 w-4" />,
    accent:
      "from-accent-red/55 via-bg-card to-text/20 border-accent-red/80 text-accent-red",
    rank: "ultimate",
  },
  {
    key: "dtp",
    title: "UNIT-06 · DTP",
    subtitle: "DAILY TREND PULLBACK",
    icon: <TrendingUp className="h-4 w-4" />,
    accent:
      "from-accent-green/40 to-bg-card border-accent-green/65 text-accent-green",
    rank: "ultimate",
  },
  {
    key: "pa",
    title: "UNIT-07 · PA",
    subtitle: "PRICE ACTION PATTERNS",
    icon: <CandlestickChart className="h-4 w-4" />,
    accent:
      "from-accent-violet/40 to-bg-card border-accent-violet/65 text-accent-violet",
    rank: "ultimate",
  },
];

export function MethodTabs() {
  const { method, setMethod, records } = useSignalsStore();
  const tabs = isEvaTheme ? EVA_TABS : OLYMPUS_TABS;

  // タブごとのアラート件数バッジ
  const alertCounts: Record<Method, number> = {
    orz: 0,
    pdhl: 0,
    both: 0,
    claude: 0,
    triple: 0,
    dtp: 0,
    pa: 0,
  };
  for (const r of records) {
    if (r.orz.is_alert) alertCounts.orz += 1;
    if (r.pdhl.is_alert) alertCounts.pdhl += 1;
    if (r.both.is_alert) alertCounts.both += 1;
    if (r.claude?.is_alert) alertCounts.claude += 1;
    if (r.triple?.is_alert) alertCounts.triple += 1;
    if (r.dtp?.is_alert) alertCounts.dtp += 1;
    if (r.pa?.is_alert) alertCounts.pa += 1;
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-2.5">
      {tabs.map((t) => {
        const active = method === t.key;
        const count = alertCounts[t.key];
        return (
          <button
            key={t.key}
            onClick={() => setMethod(t.key)}
            className={cn(
              "relative overflow-hidden rounded-2xl border p-3 text-left transition",
              "flex items-start gap-2.5 min-h-[76px]",
              isEvaTheme && "eva-frame",
              active
                ? cn("bg-gradient-to-br", t.accent, "shadow-glow")
                : "border-border/60 bg-bg-soft/40 text-text-dim hover:text-accent-ivory hover:border-accent-gold/40",
              t.rank === "ultimate" && !active && "border-accent-gold/30",
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
                <span
                  className={cn(
                    "text-[13px] font-semibold leading-tight",
                    isEvaTheme && "eva-display font-black text-[14px]",
                  )}
                >
                  {t.title}
                </span>
                {count > 0 && (
                  <span
                    className={cn(
                      "px-1.5 py-0.5 rounded-full text-[10px] font-bold font-mono",
                      active
                        ? "bg-bg-card/80"
                        : t.rank === "ultimate"
                          ? "bg-accent-gold/25 text-accent-gold"
                          : "bg-accent-gold/20 text-accent-gold",
                    )}
                  >
                    {count}
                  </span>
                )}
                {t.reference && (
                  <span
                    className="px-1.5 py-0.5 rounded-full text-[9px] font-bold border border-text-faint/40 text-text-faint"
                    title="+EV 検証で降格。参考表示のみ（アラート対象外）"
                  >
                    参考
                  </span>
                )}
              </div>
              <div className="text-[10px] opacity-75 mt-0.5 truncate">{t.subtitle}</div>
            </div>
            {active && <div className="absolute inset-x-0 bottom-0 h-0.5 bg-accent-gradient" />}
          </button>
        );
      })}
    </div>
  );
}
