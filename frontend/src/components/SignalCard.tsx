"use client";

import { motion } from "framer-motion";
import { Pin, PinOff, Sparkles, ArrowDownCircle, ArrowUpCircle, MinusCircle } from "lucide-react";
import type { Signal } from "@/lib/types";
import { cn, formatPrice } from "@/lib/utils";
import { DirectionBadge } from "./DirectionBadge";
import { ScoreGauge } from "./ScoreGauge";

interface Props {
  signal: Signal;
  pinned: boolean;
  onSelect: () => void;
  onTogglePin: () => void;
  threshold: number;
}

function computeRR(signal: Signal): number | null {
  const { price, stop_loss, take_profit, direction } = signal;
  if (price == null || stop_loss == null || take_profit == null) return null;
  const risk = Math.abs(price - stop_loss);
  const reward = Math.abs(take_profit - price);
  if (risk === 0) return null;
  // direction mismatch sanity-check
  if (direction === "long" && (stop_loss >= price || take_profit <= price)) return null;
  if (direction === "short" && (stop_loss <= price || take_profit >= price)) return null;
  return reward / risk;
}

export function SignalCard({ signal, pinned, onSelect, onTogglePin, threshold }: Props) {
  const isAlert = signal.is_alert;
  const hasTrigger = signal.has_trigger;
  const rr = computeRR(signal);

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      whileHover={{ y: -2 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      onClick={onSelect}
      className={cn(
        "group relative cursor-pointer rounded-2xl glass glass-hover p-4 shadow-card",
        "flex flex-col gap-3",
        isAlert && "ring-1 ring-accent-amber/50",
      )}
    >
      {/* Glow border on alert */}
      {isAlert && (
        <div className="pointer-events-none absolute -inset-px rounded-2xl bg-accent-gradient opacity-20 blur-sm" />
      )}

      <div className="relative flex items-start justify-between gap-2">
        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[17px] font-semibold tracking-tight">
              {signal.pair}
            </span>
            {hasTrigger && (
              <Sparkles className="h-3.5 w-3.5 text-accent-amber animate-pulse-soft" />
            )}
          </div>
          <span className="text-[11px] text-text-faint font-mono">{signal.symbol}</span>
        </div>
        <div className="flex items-center gap-2">
          <DirectionBadge direction={signal.direction} isAlert={isAlert} hasTrigger={hasTrigger} />
          <button
            onClick={(e) => {
              e.stopPropagation();
              onTogglePin();
            }}
            className="rounded-md p-1 text-text-faint hover:text-text hover:bg-bg-hover transition"
            aria-label="pin"
          >
            {pinned ? <Pin className="h-3.5 w-3.5 text-accent-cyan" /> : <PinOff className="h-3.5 w-3.5" />}
          </button>
        </div>
      </div>

      {/* 買い / 売り / 様子見 推奨 */}
      <DirectionRecommend direction={signal.direction} isAlert={isAlert} hasTrigger={hasTrigger} />

      <div className="relative">
        <div className="flex items-baseline justify-between mb-1.5">
          <span className="text-[11px] text-text-dim uppercase tracking-wider">Score</span>
          <span className="font-mono text-lg font-semibold">
            {signal.score}
            <span className="text-[11px] text-text-faint">/100</span>
          </span>
        </div>
        <ScoreGauge score={signal.score} threshold={threshold} />
      </div>

      <div className="relative flex items-center justify-between gap-2">
        <EntryTypeBadge type={signal.entry_type} />
        {signal.mt?.clarity !== undefined && (
          <span className="text-[9px] font-mono text-text-faint uppercase tracking-wider">
            明瞭度 {signal.mt.clarity}/100
          </span>
        )}
      </div>

      <div className="relative grid grid-cols-3 gap-2 text-[11px]">
        <TFTag label="日足" direction={signal.lt?.direction} />
        <TFTag label="4H" direction={signal.mt?.direction} emphasis />
        <TFTag label="15M" direction={signal.st?.direction} />
      </div>

      {/* Entry / SL / TP block */}
      <div className="relative rounded-lg border border-border/40 bg-bg-soft/40 p-2 space-y-1">
        <EntryRow
          label="指値目安"
          value={signal.price}
          sub="(成行 = 現在値)"
          accent="neutral"
        />
        <EntryRow
          label="損切 SL"
          value={signal.stop_loss}
          accent="red"
        />
        <EntryRow
          label="利確 TP"
          value={signal.take_profit}
          sub={rr ? `RR ${rr.toFixed(2)}` : undefined}
          accent="green"
        />
      </div>

      {/* PDH / PDL mini row (全通貨共通) */}
      <div className="relative grid grid-cols-2 gap-2 text-[10px] border-t border-border/40 pt-2">
        <div className="flex flex-col">
          <span className="text-text-faint">前日高値</span>
          <span className="font-mono text-accent-green">
            {formatPrice(signal.pdh ?? null)}
          </span>
        </div>
        <div className="flex flex-col items-end">
          <span className="text-text-faint">前日安値</span>
          <span className="font-mono text-accent-red">
            {formatPrice(signal.pdl ?? null)}
          </span>
        </div>
      </div>
    </motion.article>
  );
}

function DirectionRecommend({
  direction,
  isAlert,
  hasTrigger,
}: {
  direction: string;
  isAlert?: boolean;
  hasTrigger?: boolean;
}) {
  if (direction === "long") {
    return (
      <div
        className={cn(
          "relative flex items-center gap-2 rounded-lg border px-3 py-2",
          "border-accent-green/40 bg-accent-green/10 text-accent-green",
          isAlert && "ring-1 ring-accent-green/50",
        )}
      >
        <ArrowUpCircle className="h-5 w-5 shrink-0" />
        <div className="flex flex-col leading-tight">
          <span className="text-[13px] font-bold">買い推奨 (LONG)</span>
          <span className="text-[9px] opacity-80">
            {isAlert ? "★ エントリーサイン点灯中" : hasTrigger ? "トリガー検出中" : "セットアップ形成中"}
          </span>
        </div>
      </div>
    );
  }
  if (direction === "short") {
    return (
      <div
        className={cn(
          "relative flex items-center gap-2 rounded-lg border px-3 py-2",
          "border-accent-red/40 bg-accent-red/10 text-accent-red",
          isAlert && "ring-1 ring-accent-red/50",
        )}
      >
        <ArrowDownCircle className="h-5 w-5 shrink-0" />
        <div className="flex flex-col leading-tight">
          <span className="text-[13px] font-bold">売り推奨 (SHORT)</span>
          <span className="text-[9px] opacity-80">
            {isAlert ? "★ エントリーサイン点灯中" : hasTrigger ? "トリガー検出中" : "セットアップ形成中"}
          </span>
        </div>
      </div>
    );
  }
  return (
    <div className="relative flex items-center gap-2 rounded-lg border border-border/60 bg-bg-soft/40 text-text-dim px-3 py-2">
      <MinusCircle className="h-5 w-5 shrink-0" />
      <div className="flex flex-col leading-tight">
        <span className="text-[13px] font-semibold">様子見 (待機)</span>
        <span className="text-[9px] opacity-70">エントリー条件未充足</span>
      </div>
    </div>
  );
}

function EntryRow({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: number | null;
  sub?: string;
  accent: "red" | "green" | "neutral";
}) {
  const color =
    accent === "red"
      ? "text-accent-red"
      : accent === "green"
        ? "text-accent-green"
        : "text-text";
  return (
    <div className="flex items-baseline justify-between">
      <span className="text-[10px] text-text-faint">{label}</span>
      <span className={cn("font-mono text-[12px]", color)}>
        {formatPrice(value)}
        {sub && <span className="ml-1 text-[9px] text-text-faint">{sub}</span>}
      </span>
    </div>
  );
}

function EntryTypeBadge({ type }: { type?: string }) {
  if (!type || type === "none") return <span className="text-[10px] text-text-faint">—</span>;
  const map: Record<string, { label: string; cls: string }> = {
    pullback: { label: "押し目/戻り", cls: "text-accent-cyan border-accent-cyan/40 bg-accent-cyan/10" },
    breakout: { label: "ブレイク", cls: "text-accent-amber border-accent-amber/40 bg-accent-amber/10" },
    range_reversal: { label: "レンジ逆張り", cls: "text-accent-purple border-accent-purple/40 bg-accent-purple/10" },
    pdhl_long_retest: { label: "PDH リテスト", cls: "text-accent-amber border-accent-amber/40 bg-accent-amber/10" },
    pdhl_short_retest: { label: "PDL リテスト", cls: "text-accent-amber border-accent-amber/40 bg-accent-amber/10" },
    both_confluence: { label: "ORZ+PDHL 合意", cls: "text-accent-purple border-accent-purple/40 bg-accent-purple/10" },
    claude_confluence_long: { label: "Claude 合流 (Long)", cls: "text-accent-green border-accent-green/40 bg-accent-green/10" },
    claude_confluence_short: { label: "Claude 合流 (Short)", cls: "text-accent-green border-accent-green/40 bg-accent-green/10" },
    triple_confluence: { label: "3 手法合意 🏆", cls: "text-accent-amber border-accent-amber/50 bg-accent-amber/10" },
    wait: { label: "待機", cls: "text-text-dim border-border/60 bg-bg-soft/40" },
  };
  const meta = map[type] ?? { label: type, cls: "text-text-dim border-border/60 bg-bg-soft" };
  return (
    <span className={cn("px-2 py-0.5 rounded-full border text-[10px] font-semibold", meta.cls)}>
      {meta.label}
    </span>
  );
}

function TFTag({
  label,
  direction,
  emphasis,
}: {
  label: string;
  direction?: string;
  emphasis?: boolean;
}) {
  const color =
    direction?.startsWith("up")
      ? "text-accent-green border-accent-green/30 bg-accent-green/5"
      : direction?.startsWith("down")
        ? "text-accent-red border-accent-red/30 bg-accent-red/5"
        : "text-text-faint border-border bg-bg-soft";

  return (
    <div
      className={cn(
        "rounded-md border px-2 py-1 flex flex-col items-center gap-0.5",
        color,
        emphasis && "ring-1 ring-accent-cyan/20",
      )}
    >
      <span className="text-[9px] uppercase tracking-wider opacity-70">{label}</span>
      <span className="text-[10px] font-semibold">
        {direction === "up" ? "↑ UP" :
         direction === "up_weak" ? "↗" :
         direction === "down" ? "↓ DN" :
         direction === "down_weak" ? "↘" :
         "—"}
      </span>
    </div>
  );
}
