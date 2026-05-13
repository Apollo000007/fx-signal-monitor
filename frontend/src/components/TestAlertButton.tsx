"use client";

import { Siren } from "lucide-react";
import { isEvaTheme } from "@/lib/visualTheme";
import { useSignalsStore } from "@/store/signals";

let testAudioCtx: AudioContext | null = null;

function playTestImpactSound(direction: "long" | "short") {
  if (typeof window === "undefined") return;
  try {
    testAudioCtx ??= new (window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
    const ctx = testAudioCtx;
    const now = ctx.currentTime;
    const up = direction === "long";

    const hit = (
      start: number,
      duration: number,
      from: number,
      to: number,
      gainValue: number,
      type: OscillatorType,
    ) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = type;
      osc.frequency.setValueAtTime(from, start);
      osc.frequency.exponentialRampToValueAtTime(to, start + duration);
      gain.gain.setValueAtTime(0.0001, start);
      gain.gain.exponentialRampToValueAtTime(gainValue, start + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(start);
      osc.stop(start + duration + 0.03);
    };

    hit(now, 0.12, up ? 780 : 520, up ? 1320 : 330, 0.16, "square");
    hit(now + 0.17, 0.12, up ? 880 : 470, up ? 1480 : 300, 0.16, "square");
    hit(now + 0.35, 0.2, up ? 1040 : 420, up ? 1720 : 250, 0.22, "sawtooth");
    hit(now + 0.6, 0.38, 96, 46, 0.26, "triangle");
  } catch {
    // Audio can fail if the browser blocks it; the visual test still works.
  }
}

export function TestAlertButton() {
  const signals = useSignalsStore((s) => s.signals);
  if (!isEvaTheme) return null;

  const fireTest = () => {
    const candidate =
      signals.find((s) => s.is_alert && s.direction !== "none") ??
      signals.find((s) => s.direction !== "none") ??
      signals[0];
    const direction =
      candidate?.direction === "short" || candidate?.direction === "long"
        ? candidate.direction
        : "long";
    const pair = candidate?.pair ?? "TEST/JPY";

    playTestImpactSound(direction);
    window.dispatchEvent(
      new CustomEvent("fx-impact-alert", {
        detail: {
          id: `test-alert:${pair}:${Date.now()}`,
          pair,
          direction,
          score: candidate?.score ?? 99,
          method: candidate?.method ?? "TEST MODE",
          triggerLabel: "テストアラート / 使徒、襲来 カットイン確認",
          at: Date.now(),
        },
      }),
    );
  };

  return (
    <button
      type="button"
      onClick={fireTest}
      className="fixed right-4 top-24 z-[60] inline-flex items-center gap-1.5 border border-accent-red bg-black/75 px-3 py-2 font-mono text-[11px] font-black text-white shadow-[4px_4px_0_rgba(208,0,0,0.45)] backdrop-blur-sm transition hover:bg-accent-red"
      title="使徒、襲来カットインをテスト"
    >
      <Siren className="h-3.5 w-3.5" />
      テストアラート
    </button>
  );
}
