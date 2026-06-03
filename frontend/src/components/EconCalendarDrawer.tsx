"use client";

import { AnimatePresence, motion } from "framer-motion";
import { X, AlertOctagon, CalendarClock } from "lucide-react";
import { useEffect, useMemo } from "react";
import type { CalendarEvent, CalendarPayload } from "@/lib/calendar";
import { impactMeta, starString, toneClasses } from "@/lib/calendar";
import { cn, formatTime } from "@/lib/utils";
import { isEvaTheme } from "@/lib/visualTheme";

/**
 * 経済カレンダー全画面ドロワー。
 * 本日の相場リスク（星）＋ 何時にどの通貨でどんな発表があるかを一覧表示。
 */
export function EconCalendarDrawer({
  open,
  payload,
  onClose,
}: {
  open: boolean;
  payload: CalendarPayload | null;
  onClose: () => void;
}) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  const risk = payload?.risk ?? null;
  const tone = risk ? toneClasses(risk.tone) : toneClasses("calm");

  const { today, upcoming } = useMemo(() => {
    const evs = payload?.events ?? [];
    const today = evs.filter((e) => e.is_today);
    const rest = evs.filter((e) => !e.is_today);
    const byDate = new Map<string, CalendarEvent[]>();
    for (const e of rest) {
      if (!byDate.has(e.jst_date)) byDate.set(e.jst_date, []);
      byDate.get(e.jst_date)!.push(e);
    }
    return {
      today,
      upcoming: Array.from(byDate.entries()).sort((a, b) => a[0].localeCompare(b[0])),
    };
  }, [payload]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          key="calendar-fullscreen"
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.98 }}
          transition={{ duration: 0.18, ease: "easeOut" }}
          className={cn(
            "fixed inset-0 z-40 bg-bg/95 backdrop-blur-md flex flex-col",
            isEvaTheme && "bg-bg backdrop-blur-none",
          )}
        >
          {/* Top bar */}
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
                title="閉じる (Esc)"
              >
                <X className="h-5 w-5" />
              </button>
              <div className="flex items-center gap-2 min-w-0">
                <CalendarClock className="h-5 w-5 text-accent-gold shrink-0" />
                <h2 className="text-lg font-semibold truncate">
                  経済カレンダー <span className="text-text-dim text-sm">/ 本日の相場リスク</span>
                </h2>
              </div>
            </div>
            <div className="text-[11px] text-text-faint font-mono">
              {payload ? `更新 ${formatTime(payload.updated_at)} · ${payload.tz}` : "—"}
            </div>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto px-4 py-5 max-w-[1100px] w-full mx-auto space-y-6">
            {/* Risk summary */}
            <section
              className={cn(
                "rounded-2xl border p-5 flex flex-col gap-3",
                tone.border,
                tone.bg,
                isEvaTheme && "eva-frame",
              )}
            >
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div>
                  <div className="text-[10px] uppercase tracking-[0.2em] text-accent-gold/80 font-serif">
                    本日の相場リスク (JST {payload?.today ?? "—"})
                  </div>
                  <div className={cn("mt-1 text-3xl font-mono font-bold tracking-[-1px]", tone.text)}>
                    {risk ? starString(risk.stars) : "☆☆☆☆☆"}
                  </div>
                  <div className={cn("mt-1 text-lg font-semibold", tone.text)}>
                    {risk?.level ?? "取得中…"}
                    {risk ? (
                      <span className="ml-2 text-xs text-text-dim font-normal">
                        スコア {risk.score} / {risk.stars}★
                      </span>
                    ) : null}
                  </div>
                </div>
                <p className="text-sm text-text-dim max-w-[420px]">
                  {risk?.summary ?? "経済カレンダーを読み込んでいます…"}
                </p>
              </div>

              {risk && risk.headline_events.length > 0 && (
                <div className="border-t border-border/40 pt-3">
                  <div className="flex items-center gap-1.5 text-[11px] text-accent-red mb-2">
                    <AlertOctagon className="h-3.5 w-3.5" />
                    本日の要警戒イベント (重要度 高)
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {risk.headline_events.map((h, i) => (
                      <span
                        key={i}
                        className="text-xs px-2 py-1 rounded-md bg-accent-red/10 border border-accent-red/30 text-text"
                      >
                        <span className="font-mono text-accent-red">{h.jst_time}</span>{" "}
                        <span className="font-semibold">{h.currency}</span> {h.title}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              <p className="text-[10px] text-text-faint">
                ※ リスクは監視中の全通貨の当日 高/中 重要度イベントを加重して算出。
                星が多い日はボラティリティ拡大・ダマシ増に注意（ロット縮小/見送りも選択肢）。
              </p>
            </section>

            {/* Today's events */}
            <section>
              <h3 className="text-xs text-text-dim uppercase mb-2">
                本日の予定 ({today.length} 件) · 時刻 JST
              </h3>
              {today.length === 0 ? (
                <div className="rounded-xl glass border border-border/50 p-6 text-center text-sm text-text-dim">
                  本日、監視通貨に関する主要な経済指標の予定はありません。
                </div>
              ) : (
                <div className="space-y-1.5">
                  {today.map((e) => (
                    <EventRow key={e.id} e={e} />
                  ))}
                </div>
              )}
            </section>

            {/* Upcoming this week */}
            {upcoming.length > 0 && (
              <section>
                <h3 className="text-xs text-text-dim uppercase mb-2">今週のこの先</h3>
                <div className="space-y-4">
                  {upcoming.map(([date, evs]) => (
                    <div key={date}>
                      <div className="text-[11px] font-mono text-accent-gold/80 mb-1.5">{date}</div>
                      <div className="space-y-1.5">
                        {evs.map((e) => (
                          <EventRow key={e.id} e={e} dim />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function EventRow({ e, dim }: { e: CalendarEvent; dim?: boolean }) {
  const im = impactMeta(e.impact);
  return (
    <div
      className={cn(
        "flex items-center gap-3 p-2.5 rounded-lg border border-border/40 bg-bg-soft/40 text-sm",
        dim && "opacity-75",
        e.is_marquee && "ring-1 ring-accent-red/40",
      )}
    >
      <span className="font-mono text-text w-12 shrink-0">{e.jst_time}</span>
      <span className="font-semibold text-accent-cyan w-10 shrink-0">{e.currency}</span>
      <span className={cn("flex items-center gap-1 w-9 shrink-0 text-[11px]", im.color)}>
        <span className={cn("h-2 w-2 rounded-full", im.dot)} />
        {im.label}
      </span>
      <span className="flex-1 min-w-0 truncate">
        {e.title}
        {e.is_marquee && (
          <span className="ml-2 text-[10px] text-accent-red">★重要</span>
        )}
      </span>
      <span className="text-[11px] text-text-faint font-mono shrink-0 hidden sm:block">
        {e.forecast ? `予 ${e.forecast}` : ""}
        {e.previous ? `  前 ${e.previous}` : ""}
      </span>
    </div>
  );
}
