"use client";

import { CalendarClock } from "lucide-react";
import type { CalendarRisk } from "@/lib/calendar";
import { starString, toneClasses } from "@/lib/calendar";
import { cn } from "@/lib/utils";

/**
 * ヘッダーに常時表示する「本日の相場リスク」星バッジ。
 * クリックで経済カレンダードロワーを開く。
 */
export function RiskBadge({
  risk,
  onClick,
}: {
  risk: CalendarRisk | null;
  onClick: () => void;
}) {
  const tone = risk ? toneClasses(risk.tone) : toneClasses("calm");
  const stars = risk ? starString(risk.stars) : "☆☆☆☆☆";
  const level = risk ? risk.level : "取得中…";

  return (
    <button
      onClick={onClick}
      title={
        risk
          ? `本日の相場リスク: ${level} (${risk.stars}/5)\n${risk.summary}\nクリックで経済カレンダーを開く (N)`
          : "経済カレンダーを開く (N)"
      }
      className={cn(
        "flex flex-col items-end px-3 py-1.5 rounded-lg border transition hover:brightness-110",
        tone.border,
        tone.bg,
      )}
    >
      <span className="flex items-center gap-1 text-[9px] uppercase tracking-[0.18em] text-accent-gold/80 font-serif">
        <CalendarClock className="h-3 w-3" />
        相場リスク
      </span>
      <span className="text-[8px] text-text-faint tracking-widest">本日 / JST</span>
      <span className={cn("font-mono text-sm font-semibold leading-none mt-0.5", tone.text)}>
        <span className="tracking-[-1px]">{stars}</span>
        <span className="ml-1.5 text-[11px]">{level}</span>
      </span>
    </button>
  );
}
