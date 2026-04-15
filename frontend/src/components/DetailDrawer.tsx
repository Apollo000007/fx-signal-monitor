"use client";

import { AnimatePresence, motion } from "framer-motion";
import { X, AlertTriangle, CheckCircle2 } from "lucide-react";
import { useState } from "react";
import { Chart } from "./Chart";
import { DirectionBadge } from "./DirectionBadge";
import { RiskCalculator } from "./RiskCalculator";
import { ScoreGauge } from "./ScoreGauge";
import type { Signal, TimeframeAnalysis } from "@/lib/types";
import { cn, formatPrice } from "@/lib/utils";

interface Props {
  signal: Signal | null;
  threshold: number;
  onClose: () => void;
}

type Tf = "long" | "mid" | "short";

export function DetailDrawer({ signal, threshold, onClose }: Props) {
  const [tf, setTf] = useState<Tf>("mid");

  return (
    <AnimatePresence>
      {signal && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-30 bg-black/60 backdrop-blur-sm"
            onClick={onClose}
          />
          <motion.aside
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 28, stiffness: 240 }}
            className="fixed top-0 right-0 z-40 h-full w-full max-w-[780px] glass border-l border-border/80 overflow-y-auto"
          >
            <div className="sticky top-0 z-10 bg-bg-card/90 backdrop-blur-xl border-b border-border/60 px-6 py-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div>
                  <div className="flex items-center gap-3">
                    <h2 className="font-mono text-2xl font-semibold tracking-tight">{signal.pair}</h2>
                    <DirectionBadge
                      direction={signal.direction}
                      isAlert={signal.is_alert}
                      hasTrigger={signal.has_trigger}
                    />
                    <span className={cn(
                      "px-2 py-0.5 rounded-full border text-[10px] font-semibold uppercase tracking-wider",
                      signal.method === "orz" && "text-accent-cyan border-accent-cyan/40 bg-accent-cyan/10",
                      signal.method === "pdhl" && "text-accent-amber border-accent-amber/40 bg-accent-amber/10",
                      signal.method === "both" && "text-accent-purple border-accent-purple/40 bg-accent-purple/10",
                      signal.method === "claude" && "text-accent-green border-accent-green/40 bg-accent-green/10",
                      signal.method === "triple" && "text-accent-amber border-accent-amber/50 bg-accent-amber/15",
                    )}>
                      {signal.method === "orz"
                        ? "ORZ手法"
                        : signal.method === "pdhl"
                          ? "PDH/PDL手法"
                          : signal.method === "both"
                            ? "ORZ+PDHL 合意"
                            : signal.method === "claude"
                              ? "Claude Confluence"
                              : "3 手法合意 🏆"}
                    </span>
                  </div>
                  <span className="text-xs text-text-faint font-mono">{signal.symbol}</span>
                </div>
              </div>
              <button
                onClick={onClose}
                className="rounded-lg p-2 text-text-dim hover:text-text hover:bg-bg-hover transition"
                aria-label="close"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="px-6 py-5 space-y-6">
              {/* Score + Entry type section */}
              <section>
                <div className="flex items-baseline justify-between mb-2">
                  <h3 className="text-xs text-text-dim uppercase tracking-widest">スコア</h3>
                  <span className="font-mono text-3xl font-bold accent-text">
                    {signal.score}
                    <span className="text-sm text-text-faint">/100</span>
                  </span>
                </div>
                <ScoreGauge score={signal.score} threshold={threshold} size="lg" showValue />
                <div className="mt-3 flex items-center flex-wrap gap-2 text-[11px]">
                  <span className="text-text-faint">戦略タイプ:</span>
                  <EntryTypePill type={signal.entry_type} />
                  {signal.mt?.regime && (
                    <span className="px-2 py-0.5 rounded-full border border-border/60 bg-bg-soft/40 text-text-dim">
                      4H: {regimeLabel(signal.mt.regime)}
                    </span>
                  )}
                  {signal.mt?.clarity !== undefined && (
                    <span className="text-text-faint font-mono">明瞭度 {signal.mt.clarity}/100</span>
                  )}
                </div>
                <div className="mt-2 text-[11px] text-text-faint">
                  {signal.is_alert
                    ? "★ 15Mトリガー発火 — エントリーサイン点灯"
                    : signal.has_trigger
                      ? "15Mトリガー検出中"
                      : "セットアップ準備段階（15Mトリガー待機）"}
                </div>
              </section>

              {/* Price block */}
              <section className="grid grid-cols-3 gap-3">
                <InfoBlock label="現在値" value={formatPrice(signal.price)} />
                <InfoBlock label="損切目安 (SL)" value={formatPrice(signal.stop_loss)} accent="red" />
                <InfoBlock label="利確目標 (TP)" value={formatPrice(signal.take_profit)} accent="green" />
              </section>

              {/* PDH / PDL info — only meaningful for pdhl/both tabs */}
              {(signal.method === "pdhl" || signal.method === "both") && (signal.pdh != null || signal.pdl != null) && (
                <section className="grid grid-cols-2 gap-3">
                  <InfoBlock label="前日高値 (PDH)" value={formatPrice(signal.pdh ?? null)} accent="green" />
                  <InfoBlock label="前日安値 (PDL)" value={formatPrice(signal.pdl ?? null)} accent="red" />
                </section>
              )}

              {/* Risk calculator */}
              <RiskCalculator signal={signal} />

              {/* Chart with tf switcher */}
              <section>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-xs text-text-dim uppercase tracking-widest">チャート</h3>
                  <div className="flex items-center gap-1 p-1 rounded-lg bg-bg-soft border border-border/60">
                    {(["long", "mid", "short"] as Tf[]).map((t) => (
                      <button
                        key={t}
                        onClick={() => setTf(t)}
                        className={cn(
                          "px-3 py-1 text-[11px] font-semibold uppercase tracking-wider rounded-md transition",
                          tf === t
                            ? "bg-accent-gradient text-white shadow-glow"
                            : "text-text-dim hover:text-text",
                        )}
                      >
                        {t === "long" ? "日足" : t === "mid" ? "4H" : "15M"}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="rounded-xl border border-border/60 bg-bg-soft/40 p-2">
                  <Chart
                    symbol={signal.symbol}
                    tf={tf}
                    height={400}
                    levels={{
                      pdh: signal.pdh ?? null,
                      pdl: signal.pdl ?? null,
                      resistances: (tf === "long" ? signal.lt?.resistances : signal.mt?.resistances) ?? [],
                      supports: (tf === "long" ? signal.lt?.supports : signal.mt?.supports) ?? [],
                      entry: signal.price,
                      stopLoss: signal.stop_loss,
                      takeProfit: signal.take_profit,
                    }}
                  />
                </div>
              </section>

              {/* Reasons */}
              <section>
                <h3 className="text-xs text-text-dim uppercase tracking-widest mb-2">根拠</h3>
                <ul className="space-y-1.5">
                  {signal.reasons.map((r, i) => (
                    <li
                      key={i}
                      className="flex items-start gap-2 text-sm p-2 rounded-lg bg-bg-soft/40 border border-border/40"
                    >
                      <CheckCircle2 className="h-4 w-4 text-accent-green/70 shrink-0 mt-0.5" />
                      <span>{r}</span>
                    </li>
                  ))}
                </ul>
              </section>

              {/* Warnings */}
              {signal.warnings.length > 0 && (
                <section>
                  <h3 className="text-xs text-accent-amber uppercase tracking-widest mb-2">警告</h3>
                  <ul className="space-y-1.5">
                    {signal.warnings.map((w, i) => (
                      <li
                        key={i}
                        className="flex items-start gap-2 text-sm p-2 rounded-lg bg-accent-amber/5 border border-accent-amber/30"
                      >
                        <AlertTriangle className="h-4 w-4 text-accent-amber shrink-0 mt-0.5" />
                        <span>{w}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {/* Timeframe details */}
              <section className="space-y-3">
                <h3 className="text-xs text-text-dim uppercase tracking-widest">時間軸別データ</h3>
                <TFDetail label="日足" tf={signal.lt} />
                <TFDetail label="4H (メイン)" tf={signal.mt} emphasis />
                <TFDetail label="15M" tf={signal.st} />
              </section>
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

function InfoBlock({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: "red" | "green";
}) {
  return (
    <div className="rounded-xl bg-bg-soft/40 border border-border/40 p-3">
      <div className="text-[10px] uppercase tracking-wider text-text-faint">{label}</div>
      <div
        className={cn(
          "font-mono text-lg mt-0.5",
          accent === "red" && "text-accent-red",
          accent === "green" && "text-accent-green",
        )}
      >
        {value}
      </div>
    </div>
  );
}

function TFDetail({
  label,
  tf,
  emphasis,
}: {
  label: string;
  tf: TimeframeAnalysis | null;
  emphasis?: boolean;
}) {
  if (!tf) {
    return (
      <div className="rounded-xl border border-border/40 bg-bg-soft/20 p-3 text-text-faint text-sm">
        {label}: データなし
      </div>
    );
  }
  return (
    <div
      className={cn(
        "rounded-xl border p-3 text-[12px]",
        emphasis ? "border-accent-cyan/30 bg-accent-cyan/5" : "border-border/40 bg-bg-soft/30",
      )}
    >
      <div className="flex items-baseline justify-between mb-2">
        <span className="font-semibold text-sm">{label}</span>
        <span
          className={cn(
            "font-mono text-[11px] px-2 py-0.5 rounded-full",
            tf.direction.startsWith("up") && "text-accent-green bg-accent-green/10",
            tf.direction.startsWith("down") && "text-accent-red bg-accent-red/10",
            tf.direction === "range" && "text-text-faint bg-bg-soft",
          )}
        >
          {tf.direction}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 font-mono">
        <Row k="終値" v={formatPrice(tf.close)} />
        <Row k="SMA20" v={formatPrice(tf.sma20)} />
        <Row k="SMA50" v={formatPrice(tf.sma50)} />
        <Row k="SMA100" v={formatPrice(tf.sma100)} />
        <Row k="SMA20傾斜" v={tf.slope20 != null ? `${tf.slope20 >= 0 ? "+" : ""}${tf.slope20.toFixed(2)}%` : "—"} />
        <Row k="SMA50傾斜" v={tf.slope50 != null ? `${tf.slope50 >= 0 ? "+" : ""}${tf.slope50.toFixed(2)}%` : "—"} />
        <Row k="雲上端" v={formatPrice(tf.cloud_top)} />
        <Row k="雲下端" v={formatPrice(tf.cloud_bottom)} />
        <Row k="価格vs雲" v={tf.price_vs_cloud} />
        <Row k="相場タイプ" v={regimeLabel(tf.regime)} />
      </div>
    </div>
  );
}

function regimeLabel(r?: string): string {
  switch (r) {
    case "trend_up": return "上昇トレンド";
    case "trend_down": return "下降トレンド";
    case "range": return "レンジ";
    case "unclear": return "不明瞭";
    default: return r ?? "—";
  }
}

function EntryTypePill({ type }: { type?: string }) {
  if (!type || type === "none") return <span className="text-text-faint">—</span>;
  const map: Record<string, { label: string; cls: string }> = {
    pullback: { label: "押し目/戻り売り", cls: "text-accent-cyan border-accent-cyan/40 bg-accent-cyan/10" },
    breakout: { label: "ブレイクアウト", cls: "text-accent-amber border-accent-amber/40 bg-accent-amber/10" },
    range_reversal: { label: "レンジ逆張り", cls: "text-accent-purple border-accent-purple/40 bg-accent-purple/10" },
    pdhl_long_retest: { label: "PDH ブレイク+リテスト (Long)", cls: "text-accent-amber border-accent-amber/40 bg-accent-amber/10" },
    pdhl_short_retest: { label: "PDL ブレイク+リテスト (Short)", cls: "text-accent-amber border-accent-amber/40 bg-accent-amber/10" },
    both_confluence: { label: "ORZ + PDHL 合意", cls: "text-accent-purple border-accent-purple/40 bg-accent-purple/10" },
    claude_confluence_long: { label: "Claude Confluence (Long)", cls: "text-accent-green border-accent-green/40 bg-accent-green/10" },
    claude_confluence_short: { label: "Claude Confluence (Short)", cls: "text-accent-green border-accent-green/40 bg-accent-green/10" },
    triple_confluence: { label: "3 手法合意 (最高勝率ゾーン) 🏆", cls: "text-accent-amber border-accent-amber/50 bg-accent-amber/10" },
    wait: { label: "待機", cls: "text-text-dim border-border/60 bg-bg-soft/40" },
  };
  const meta = map[type] ?? { label: type, cls: "text-text-dim border-border/60 bg-bg-soft" };
  return (
    <span className={cn("px-2 py-0.5 rounded-full border text-[10px] font-semibold", meta.cls)}>
      {meta.label}
    </span>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-text-faint">{k}</span>
      <span>{v}</span>
    </div>
  );
}
