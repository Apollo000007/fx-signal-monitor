"use client";

import { AnimatePresence, motion } from "framer-motion";
import { X, AlertTriangle, CheckCircle2, PanelRightClose, PanelRightOpen, Radio } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Chart } from "./Chart";
import { DirectionBadge } from "./DirectionBadge";
import { RiskCalculator } from "./RiskCalculator";
import { ScoreGauge } from "./ScoreGauge";
import type { LivePrice } from "@/lib/oanda";
import { pipSize } from "@/lib/oanda";
import { computeMMLevels } from "@/lib/mm";
import type { ChartTf, Signal, TimeframeAnalysis } from "@/lib/types";
import { cn, formatPrice } from "@/lib/utils";
import { isEvaTheme } from "@/lib/visualTheme";

interface Props {
  signal: Signal | null;
  threshold: number;
  live?: LivePrice | null;
  onClose: () => void;
}

const TF_OPTIONS: { key: ChartTf; label: string }[] = [
  { key: "week", label: "週足" },
  { key: "long", label: "日足" },
  { key: "mid", label: "4H" },
  { key: "h1", label: "1H" },
  { key: "short", label: "15M" },
  { key: "m5", label: "5M" },
  { key: "m1", label: "1M" },
];

const TF_STORAGE_KEY = "fxsig:detail-drawer:tf";
const VALID_TF_KEYS = new Set<ChartTf>(TF_OPTIONS.map((o) => o.key));

function loadStoredTf(): ChartTf {
  if (typeof window === "undefined") return "mid";
  try {
    const raw = window.localStorage.getItem(TF_STORAGE_KEY);
    if (raw && VALID_TF_KEYS.has(raw as ChartTf)) return raw as ChartTf;
  } catch {
    // localStorage 無効環境 (シークレット等) は黙ってデフォルト
  }
  return "mid";
}

/** チャートTF → どの分析レコード(lt/mt/ht/st)からS/Rを引いてくるか */
function tfToAnalysis(tf: ChartTf, signal: Signal): TimeframeAnalysis | null {
  switch (tf) {
    case "week":
    case "long":
      return signal.lt;
    case "mid":
      return signal.mt;
    case "h1":
      return signal.ht ?? signal.mt;
    case "short":
    case "m5":
    case "m1":
      return signal.st;
    default:
      return signal.mt;
  }
}

export function DetailDrawer({ signal, threshold, live, onClose }: Props) {
  // SSR/CSR ハイドレーション差異を避けるため、初期値はデフォルトで描画→マウント後に復元
  const [tf, setTf] = useState<ChartTf>("mid");
  const [sidebarOpen, setSidebarOpen] = useState(true);

  useEffect(() => {
    setTf(loadStoredTf());
  }, []);
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(TF_STORAGE_KEY, tf);
    } catch {
      // 書き込めない環境では黙って無視
    }
  }, [tf]);

  // ESC でドロワーを閉じる
  useEffect(() => {
    if (!signal) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [signal, onClose]);

  const chartLevels = useMemo(() => {
    if (!signal) return undefined;
    const a = tfToAnalysis(tf, signal);
    // --- 資産管理 (Money-Management) 利確ラインを算出 ---
    // SL は構造 SL (= 1R)。利確は R の倍数: メイン = 最低 2R、推奨 3R。
    // RR 2 → 損益分岐 勝率 33%、RR 3 → 同 25%。低勝率でも資産が残る構成。
    const mm = computeMMLevels(signal);
    return {
      pdh: signal.pdh ?? null,
      pdl: signal.pdl ?? null,
      resistances: a?.resistances ?? [],
      supports: a?.supports ?? [],
      entry: signal.price,
      stopLoss: signal.stop_loss,
      // メイン利確: 最低 2R (構造 TP が 2R より遠ければそちらを採用)
      takeProfit: mm ? mm.primaryTp : signal.take_profit,
      mmTp3R: mm ? mm.tp3R : null,
    };
  }, [signal, tf]);

  const mm = useMemo(() => (signal ? computeMMLevels(signal) : null), [signal]);

  return (
    <AnimatePresence>
      {signal && (
        <motion.div
          key="detail-fullscreen"
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.98 }}
          transition={{ duration: 0.18, ease: "easeOut" }}
          className={cn(
            "fixed inset-0 z-40 bg-bg/95 backdrop-blur-md flex flex-col",
            isEvaTheme && "bg-bg backdrop-blur-none",
          )}
        >
          {/* Top bar: ✕ on the LEFT, then pair / badge / method. Right side: TF + sidebar toggle */}
          <div
            className={cn(
              "flex items-center justify-between gap-3 px-3 py-2.5 border-b border-border/60 bg-bg-card/70 flex-wrap",
              isEvaTheme && "border-b-4 border-accent-red bg-bg-card/90",
            )}
          >
            <div className="flex items-center gap-3 min-w-0">
              <button
                onClick={onClose}
                className="rounded-lg p-2 text-text-dim hover:text-accent-red hover:bg-bg-hover hover:border-accent-red/40 transition border border-border/60 shrink-0"
                aria-label="close"
                title="閉じる (Esc) — 一覧へ戻る"
              >
                <X className="h-5 w-5" />
              </button>
              <h2
                className={cn(
                  "font-mono text-2xl font-semibold truncate",
                  isEvaTheme && "eva-display text-3xl font-black",
                )}
              >
                {signal.pair}
              </h2>
              <DirectionBadge
                direction={signal.direction}
                isAlert={signal.is_alert}
                hasTrigger={signal.has_trigger}
              />
              <span
                className={cn(
                  "px-2 py-0.5 rounded-full border text-[10px] font-semibold uppercase hidden md:inline",
                  signal.method === "orz" && "text-accent-cyan border-accent-cyan/40 bg-accent-cyan/10",
                  signal.method === "pdhl" && "text-accent-amber border-accent-amber/40 bg-accent-amber/10",
                  signal.method === "both" && "text-accent-purple border-accent-purple/40 bg-accent-purple/10",
                  signal.method === "claude" && "text-accent-green border-accent-green/40 bg-accent-green/10",
                  signal.method === "triple" && "text-accent-amber border-accent-amber/50 bg-accent-amber/15",
                  signal.method === "dtp" && "text-accent-green border-accent-green/50 bg-accent-green/15",
                )}
              >
                {signal.method === "orz"
                  ? isEvaTheme ? "OPS-01 ORZ" : "ORZ手法"
                  : signal.method === "pdhl"
                    ? isEvaTheme ? "OPS-02 PDH/PDL" : "PDH/PDL手法"
                    : signal.method === "both"
                      ? isEvaTheme ? "SYNC-03 合流" : "ORZ+PDHL 合意"
                      : signal.method === "claude"
                        ? isEvaTheme ? "AI-04 Claude" : "Claude Confluence"
                        : signal.method === "dtp"
                          ? isEvaTheme ? "UNIT-06 DTP" : "DTP 日足トレンド押し目"
                          : isEvaTheme ? "FINAL-05 三手法" : "3 手法合意 🏆"}
              </span>
              <span className="text-xs text-text-faint font-mono hidden lg:inline">
                {signal.symbol}
              </span>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <div className="flex items-center gap-1 p-1 rounded-lg bg-bg-soft border border-border/60 flex-wrap">
                {TF_OPTIONS.map((opt) => (
                  <button
                    key={opt.key}
                    onClick={() => setTf(opt.key)}
                    className={cn(
                      "px-2.5 py-1 text-[11px] font-semibold uppercase rounded-md transition",
                      tf === opt.key
                        ? "bg-accent-gradient text-white shadow-glow"
                        : "text-text-dim hover:text-text",
                    )}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
              <button
                onClick={() => setSidebarOpen((v) => !v)}
                className="hidden md:flex items-center gap-1.5 rounded-lg p-2 text-text-dim hover:text-text hover:bg-bg-hover transition border border-border/60"
                title={sidebarOpen ? "サイドパネルを隠す" : "サイドパネルを表示"}
                aria-label="toggle sidebar"
              >
                {sidebarOpen ? (
                  <PanelRightClose className="h-4 w-4" />
                ) : (
                  <PanelRightOpen className="h-4 w-4" />
                )}
              </button>
            </div>
          </div>

          {/* Main: chart (large) + details sidebar */}
          <div className="flex-1 flex min-h-0 flex-col md:flex-row">
            {/* Chart pane — ドンっと大きく */}
            <div className={cn("flex-1 min-h-[55vh] md:min-h-0 p-3", isEvaTheme && "bg-bg")}>
              <Chart
                symbol={signal.symbol}
                tf={tf}
                fillParent
                levels={chartLevels}
                liveMid={live?.mid ?? null}
              />
            </div>

            {/* Details sidebar */}
            {sidebarOpen && (
              <aside
                className={cn(
                  "md:w-[360px] lg:w-[400px] shrink-0 border-t md:border-t-0 md:border-l border-border/60 bg-bg-card/40 overflow-y-auto",
                  isEvaTheme && "bg-bg-card",
                )}
              >
                <div className="px-5 py-5 space-y-5">
                  {/* Score + Entry type section */}
                  <section>
                <div className="flex items-baseline justify-between mb-2">
                  <h3 className="text-xs text-text-dim uppercase">スコア</h3>
                  <span className="font-mono text-3xl font-bold accent-text">
                    {signal.score}
                    <span className="text-sm text-text-faint">/100</span>
                  </span>
                </div>
                <ScoreGauge score={signal.score} threshold={threshold} size="lg" showValue />
                <div className="mt-3 flex items-center flex-wrap gap-2 text-[11px]">
                  <span className="text-text-faint">戦略タイプ:</span>
                  {signal.method === "pa" && signal.pattern_name ? (
                    <span
                      className={cn(
                        "px-2 py-0.5 rounded-full border font-semibold",
                        signal.rank === "S"
                          ? "text-accent-red border-accent-red/50 bg-accent-red/10"
                          : signal.rank === "A"
                            ? "text-accent-amber border-accent-amber/50 bg-accent-amber/10"
                            : "text-accent-cyan border-accent-cyan/40 bg-accent-cyan/10",
                      )}
                    >
                      {signal.rank ? `【${signal.rank}】` : ""}{signal.pattern_name}
                    </span>
                  ) : (
                    <EntryTypePill type={signal.entry_type} />
                  )}
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
                    ? isEvaTheme ? "! 15Mトリガー発火 — エントリーサイン点灯" : "★ 15Mトリガー発火 — エントリーサイン点灯"
                    : signal.has_trigger
                      ? "15Mトリガー検出中"
                      : "セットアップ準備段階（15Mトリガー待機）"}
                </div>
              </section>

              {/* Live price banner — OANDA ライブ値があれば大きく表示、各レベルへの距離も pips で */}
              {live?.mid != null && (
                <LiveLevelDistance signal={signal} live={live} />
              )}

              {/* Price block */}
              <section className="grid grid-cols-3 gap-3">
                <InfoBlock label="現在値" value={formatPrice(signal.price)} />
                <InfoBlock label="損切目安 (SL · 1R)" value={formatPrice(signal.stop_loss)} accent="red" />
                <InfoBlock
                  label={mm ? `利確目標 (最低2R · RR${mm.rr.toFixed(1)})` : "利確目標 (TP)"}
                  value={formatPrice(mm ? mm.primaryTp : signal.take_profit)}
                  accent="green"
                />
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

              {/* Reasons */}
              <section>
                <h3 className="text-xs text-text-dim uppercase mb-2">根拠</h3>
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
                  <h3 className="text-xs text-accent-amber uppercase mb-2">警告</h3>
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
                    <h3 className="text-xs text-text-dim uppercase">時間軸別データ</h3>
                    <TFDetail label="日足" tf={signal.lt} />
                    <TFDetail label="4H (メイン)" tf={signal.mt} emphasis />
                    {signal.ht && <TFDetail label="1H (合意補助)" tf={signal.ht} />}
                    <TFDetail label="15M" tf={signal.st} />
                  </section>
                </div>
              </aside>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/** OANDA ライブ価格と各キーレベルの距離を pips で表示するパネル */
function LiveLevelDistance({
  signal,
  live,
}: {
  signal: Signal;
  live: LivePrice;
}) {
  const mid = live.mid;
  if (mid == null) return null;
  const ps = pipSize(live.instrument);
  const mm = computeMMLevels(signal);
  type LevelRow = { label: string; price: number | null | undefined; accent: "red" | "green" | "neutral" };
  const rows: LevelRow[] = (
    [
      { label: "前日高値 (PDH)", price: signal.pdh ?? null, accent: "green" },
      { label: "前日安値 (PDL)", price: signal.pdl ?? null, accent: "red" },
      { label: "エントリー", price: signal.price, accent: "neutral" },
      { label: "損切り (SL · 1R)", price: signal.stop_loss, accent: "red" },
      { label: "利確 最低2R", price: mm ? mm.primaryTp : signal.take_profit, accent: "green" },
      { label: "利確 推奨3R", price: mm ? mm.tp3R : null, accent: "green" },
    ] as LevelRow[]
  ).filter((r) => r.price != null);

  return (
    <section className={cn("rounded-xl border border-accent-green/35 bg-accent-green/5 p-3", isEvaTheme && "eva-frame")}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 text-[11px] uppercase text-accent-green">
          <Radio className="h-3.5 w-3.5 animate-pulse-soft" />
          ライブ価格 (OANDA tick)
        </div>
        <div className="font-mono text-[22px] font-bold text-accent-ivory tabular-nums">
          {formatPrice(mid)}
        </div>
      </div>
      <div className="text-[10px] text-text-faint mb-2 font-mono">
        bid {formatPrice(live.bid)} / ask {formatPrice(live.ask)} ·{" "}
        {new Date(live.time).toLocaleTimeString("ja-JP")}
      </div>
      <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] font-mono">
        {rows.map((r) => {
          const diff = mid - (r.price as number);
          const pips = diff / ps;
          const sign = pips >= 0 ? "+" : "";
          const color =
            r.accent === "red"
              ? "text-accent-red"
              : r.accent === "green"
                ? "text-accent-green"
                : "text-text";
          return (
            <div key={r.label} className="flex justify-between">
              <span className="text-text-faint">{r.label}</span>
              <span className={color}>
                {sign}
                {pips.toFixed(1)} pips
              </span>
            </div>
          );
        })}
      </div>
      <div className="mt-2 text-[10px] text-text-faint leading-relaxed">
        ※ 価格がいずれかのレベルを跨いだ瞬間にブラウザ通知 + 音が鳴ります (同一クロスは 5 分クールダウン)。
      </div>
    </section>
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
      <div className="text-[10px] uppercase text-text-faint">{label}</div>
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
    triple_confluence: { label: isEvaTheme ? "3 手法合意 (最高勝率ゾーン)" : "3 手法合意 (最高勝率ゾーン) 🏆", cls: "text-accent-amber border-accent-amber/50 bg-accent-amber/10" },
    dtp_long: { label: "DTP 日足トレンド押し目買い", cls: "text-accent-green border-accent-green/40 bg-accent-green/10" },
    dtp_short: { label: "DTP 日足トレンド戻り売り", cls: "text-accent-green border-accent-green/40 bg-accent-green/10" },
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
