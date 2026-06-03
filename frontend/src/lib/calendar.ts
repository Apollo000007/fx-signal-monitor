/**
 * FX 経済カレンダー + 当日相場リスクスコアの型定義 + フェッチ関数。
 *
 * cron (news_calendar.py) が `frontend/public/api/calendar.json` を書き出すので、
 * フロントは静的にそれを fetch する (paper.json と同方式)。
 */

export type RiskTone = "calm" | "watch" | "warn" | "high";

export interface CalendarHeadline {
  currency: string;
  title: string;
  jst_time: string;
}

export interface CalendarRisk {
  score: number;
  /** 1〜5 */
  stars: number;
  /** 平時 / やや注意 / 注意 / 警戒 / 高警戒 */
  level: string;
  tone: RiskTone;
  summary: string;
  headline_events: CalendarHeadline[];
}

export interface CalendarEvent {
  id: string;
  currency: string;
  /** High / Medium / Low / Holiday */
  impact: string;
  title: string;
  forecast: string;
  previous: string;
  jst_iso: string;
  jst_date: string;
  jst_time: string;
  is_today: boolean;
  is_marquee: boolean;
}

export interface CalendarPayload {
  updated_at: string;
  tz: string;
  /** JST の今日 (YYYY-MM-DD) */
  today: string;
  ok: boolean;
  risk: CalendarRisk;
  events: CalendarEvent[];
}

export async function fetchCalendar(): Promise<CalendarPayload | null> {
  try {
    const res = await fetch(`/api/calendar.json?t=${Math.floor(Date.now() / 300000)}`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as CalendarPayload;
  } catch {
    return null;
  }
}

/** tone → Tailwind カラークラス (border / bg / text) */
export function toneClasses(tone: RiskTone): { border: string; bg: string; text: string; dot: string } {
  switch (tone) {
    case "high":
      return { border: "border-accent-red/55", bg: "bg-accent-red/12", text: "text-accent-red", dot: "bg-accent-red" };
    case "warn":
      return { border: "border-accent-amber/55", bg: "bg-accent-amber/12", text: "text-accent-amber", dot: "bg-accent-amber" };
    case "watch":
      return { border: "border-accent-gold/50", bg: "bg-accent-gold/10", text: "text-accent-gold", dot: "bg-accent-gold" };
    default:
      return { border: "border-accent-green/45", bg: "bg-accent-green/10", text: "text-accent-green", dot: "bg-accent-green" };
  }
}

/** 重要度 → 色 + 日本語ラベル */
export function impactMeta(impact: string): { label: string; color: string; dot: string } {
  switch (impact) {
    case "High":
      return { label: "高", color: "text-accent-red", dot: "bg-accent-red" };
    case "Medium":
      return { label: "中", color: "text-accent-amber", dot: "bg-accent-amber" };
    case "Holiday":
      return { label: "休", color: "text-text-faint", dot: "bg-text-faint" };
    default:
      return { label: "低", color: "text-text-dim", dot: "bg-text-dim" };
  }
}

export function starString(stars: number): string {
  const n = Math.max(1, Math.min(5, Math.round(stars)));
  return "★".repeat(n) + "☆".repeat(5 - n);
}
