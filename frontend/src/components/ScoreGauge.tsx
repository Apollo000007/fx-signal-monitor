"use client";

import { motion } from "framer-motion";
import { cn, scoreColor } from "@/lib/utils";

interface Props {
  score: number;
  threshold?: number;
  size?: "sm" | "md" | "lg";
  /** true で中央に数値を重ねる (lg のみ) */
  showValue?: boolean;
}

/**
 * スコアの棒グラフ。
 *  - 背景は濃いネイビーにして塗りの輝度を立たせる
 *  - 塗りは常に見える最低幅 (6%) を確保
 *  - アラート閾値を超えたら塗りが pulse する
 *  - threshold マーカーは白 + グロー
 */
export function ScoreGauge({ score, threshold = 75, size = "md", showValue }: Props) {
  const pct = Math.max(0, Math.min(100, score));
  const gradient = scoreColor(pct);
  const height = size === "sm" ? "h-1.5" : size === "lg" ? "h-4" : "h-2";
  const fillPct = Math.max(pct, 6);
  const isAlert = pct >= threshold;

  return (
    <div className="w-full">
      <div
        className={cn(
          "relative w-full rounded-full overflow-hidden",
          // 濃いネイビー + 内側シャドウで凹んだ感じ
          "bg-[#0b1220] ring-1 ring-white/10",
          "shadow-[inset_0_1px_2px_rgba(0,0,0,0.6)]",
          height,
        )}
      >
        {/* ダークなトラック上の薄いハッシュ (目盛感) */}
        <div
          className="absolute inset-0 opacity-30 pointer-events-none"
          style={{
            backgroundImage:
              "repeating-linear-gradient(90deg, rgba(255,255,255,0.05) 0, rgba(255,255,255,0.05) 1px, transparent 1px, transparent 10%)",
          }}
        />

        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${fillPct}%` }}
          transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
          className={cn(
            "relative h-full rounded-full bg-gradient-to-r",
            // グロー強め
            "shadow-[0_0_14px_rgba(34,211,238,0.55),0_0_4px_rgba(255,255,255,0.35)_inset]",
            gradient,
            isAlert && "animate-pulse-soft",
          )}
          style={{ opacity: pct === 0 ? 0.55 : 1 }}
        >
          {/* 先端の光沢 */}
          <div className="absolute right-0 top-0 h-full w-1 bg-white/70 rounded-r-full blur-[1px]" />
        </motion.div>

        {/* threshold marker — 白 + 下にラベル */}
        <div
          className="absolute top-0 bottom-0 w-[2px] bg-white/90 shadow-[0_0_6px_rgba(255,255,255,0.8)]"
          style={{ left: `${threshold}%` }}
          title={`閾値 ${threshold}`}
        />

        {/* 中央の数値 (lg のみ) */}
        {showValue && size === "lg" && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <span className="text-[11px] font-mono font-bold text-white drop-shadow-[0_1px_2px_rgba(0,0,0,0.9)]">
              {pct}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
