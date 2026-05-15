"use client";

import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, Crosshair, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import { isEvaTheme } from "@/lib/visualTheme";
import { useSignalsStore, type Toast } from "@/store/signals";

interface ImpactAlert {
  id: string;
  pair: string;
  direction: "long" | "short";
  score?: number;
  method?: string;
  triggerLabel?: string;
  at: number;
}

function methodLabel(method?: string) {
  switch (method) {
    case "orz":
      return "OPS-01 ORZ";
    case "pdhl":
      return "OPS-02 PDH/PDL";
    case "both":
      return "SYNC-03 合流";
    case "claude":
      return "AI-04 Claude";
    case "triple":
      return "FINAL-05 三手法";
    case "dtp":
      return "UNIT-06 DTP";
    default:
      return method ?? "LIVE LEVEL";
  }
}

function fromToast(t: Toast): ImpactAlert {
  return {
    id: t.id,
    pair: t.pair,
    direction: t.direction,
    score: t.score,
    method: t.method,
    triggerLabel: t.direction === "long" ? "LONG トリガー発火" : "SHORT トリガー発火",
    at: t.at,
  };
}

export function AlertImpactOverlay() {
  const { toasts, dismissToast, setSelected } = useSignalsStore();
  const latestToast = toasts[toasts.length - 1] ?? null;
  const [impact, setImpact] = useState<ImpactAlert | null>(null);

  useEffect(() => {
    if (!latestToast) return;
    setImpact(fromToast(latestToast));
  }, [latestToast]);

  useEffect(() => {
    const onImpact = (event: Event) => {
      const detail = (event as CustomEvent<ImpactAlert>).detail;
      if (detail?.id && detail?.pair) setImpact(detail);
    };
    window.addEventListener("fx-impact-alert", onImpact);
    return () => window.removeEventListener("fx-impact-alert", onImpact);
  }, []);

  useEffect(() => {
    if (!impact) return;
    const id = window.setTimeout(() => setImpact(null), 5600);
    return () => window.clearTimeout(id);
  }, [impact]);

  const directionLabel = impact?.direction === "long" ? "買撃" : "売撃";
  const tone = impact?.direction === "long" ? "text-accent-green" : "text-accent-red";
  const subtitle = useMemo(() => {
    if (!impact) return "";
    const score = impact.score != null ? ` / SCORE ${impact.score}` : "";
    return `${methodLabel(impact.method)}${score}`;
  }, [impact]);

  if (!isEvaTheme) return null;

  return (
    <AnimatePresence>
      {impact && (
        <motion.div
          key={impact.id}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.16 }}
          className="fixed inset-0 z-[80] overflow-hidden bg-black text-white"
          role="alertdialog"
          aria-label={`${impact.pair} alert`}
        >
          <div
            aria-hidden
            className="absolute inset-0 bg-cover bg-center alert-impact-bg"
          />
          <div aria-hidden className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(0,0,0,0.05),rgba(0,0,0,0.68)_62%,rgba(0,0,0,0.94))]" />
          <div aria-hidden className="absolute inset-0 alert-scanline opacity-45" />
          <div aria-hidden className="absolute left-0 top-0 h-full w-5 eva-stripe" />
          <div aria-hidden className="absolute right-0 top-0 h-full w-5 eva-stripe" />

          <button
            type="button"
            onClick={() => {
              setImpact(null);
              dismissToast(impact.id);
            }}
            className="absolute right-5 top-5 z-20 border border-white/70 bg-black/60 p-2 text-white hover:bg-accent-red"
            aria-label="閉じる"
          >
            <X className="h-6 w-6" />
          </button>

          <div className="relative z-10 flex min-h-screen flex-col items-center justify-center px-6 text-center">
            <motion.div
              initial={{ scale: 0.7, opacity: 0, rotate: -1 }}
              animate={{ scale: [1.12, 0.98, 1], opacity: 1, rotate: [0, -0.5, 0.5, 0] }}
              transition={{ duration: 0.62, ease: [0.16, 1, 0.3, 1] }}
              className="alert-impact-panel w-full max-w-5xl border-4 border-white bg-black/72 px-5 py-6 shadow-[0_0_0_8px_rgba(208,0,0,0.75),0_0_60px_rgba(208,0,0,0.8)] md:px-10 md:py-8"
            >
              <div className="mb-4 flex items-center justify-center gap-3 text-accent-red">
                <AlertTriangle className="h-9 w-9 animate-pulse" />
                <span className="eva-display text-3xl font-black md:text-5xl">警報</span>
                <AlertTriangle className="h-9 w-9 animate-pulse" />
              </div>

              <motion.div
                initial={{ letterSpacing: "0.28em", opacity: 0 }}
                animate={{ letterSpacing: "0em", opacity: 1 }}
                transition={{ delay: 0.08, duration: 0.34 }}
                className="eva-display alert-kanji text-[clamp(4rem,14vw,11rem)] font-black leading-[0.86] text-white"
              >
                使徒、襲来
              </motion.div>

              <div className="mx-auto my-5 h-2 max-w-3xl bg-accent-red" />

              <div className="grid gap-3 md:grid-cols-[1fr_auto_1fr] md:items-center">
                <div className="border border-white/50 bg-white px-4 py-3 text-left text-black">
                  <div className="text-[11px] font-bold uppercase text-accent-red">TARGET PAIR</div>
                  <div className="eva-display text-4xl font-black md:text-6xl">{impact.pair}</div>
                </div>

                <div className={cn("eva-display px-5 py-3 text-5xl font-black md:text-7xl", tone)}>
                  {directionLabel}
                </div>

                <div className="border border-white/50 bg-black px-4 py-3 text-left">
                  <div className="text-[11px] font-bold uppercase text-accent-red">ALERT SOURCE</div>
                  <div className="font-mono text-lg font-bold md:text-2xl">{subtitle}</div>
                  <div className="mt-1 text-sm text-white/75">{impact.triggerLabel}</div>
                </div>
              </div>

              <button
                type="button"
                onClick={() => {
                  setSelected(impact.pair);
                  dismissToast(impact.id);
                  setImpact(null);
                }}
                className="mt-6 inline-flex items-center gap-2 border-2 border-accent-red bg-white px-5 py-3 font-mono text-sm font-black text-black transition hover:bg-accent-red hover:text-white"
              >
                <Crosshair className="h-4 w-4" />
                該当シグナルを確認
              </button>
            </motion.div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
