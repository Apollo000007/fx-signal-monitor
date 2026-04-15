"use client";

import { Sun, Zap, Volume2, VolumeX, Keyboard } from "lucide-react";
import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { useSignalsStore } from "@/store/signals";
import { cn, formatTime } from "@/lib/utils";

export function Header() {
  const { updatedAt, config, signals, loading, soundEnabled, toggleSound } = useSignalsStore();
  const alertCount = signals.filter((s) => s.is_alert).length;

  // 1秒ごとに「最後の更新からの経過秒」を再計算して鮮度バーを更新
  const [, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(id);
  }, []);

  const ageSec = updatedAt ? (Date.now() - new Date(updatedAt).getTime()) / 1000 : Infinity;
  const freshnessTone: "fresh" | "ok" | "stale" =
    ageSec < 60 ? "fresh" : ageSec < 180 ? "ok" : "stale";

  const [showShortcuts, setShowShortcuts] = useState(false);

  return (
    <header className="mb-8 relative">
      {/* Mandala / halo decoration behind title */}
      <div
        aria-hidden
        className="pointer-events-none absolute left-0 top-0 -translate-y-1/4 w-72 h-72 rounded-full bg-aura-gradient opacity-25 blur-3xl animate-aura-breathe"
      />

      <div className="relative flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-4">
          <motion.div
            initial={{ scale: 0.8, opacity: 0, rotate: -20 }}
            animate={{ scale: 1, opacity: 1, rotate: 0 }}
            transition={{ type: "spring", stiffness: 220, damping: 18 }}
            className="relative h-14 w-14 rounded-full flex items-center justify-center"
          >
            {/* spinning outer halo */}
            <div className="absolute inset-0 rounded-full bg-accent-gradient opacity-90 blur-[1px] animate-halo-spin" />
            <div className="absolute inset-[3px] rounded-full bg-bg-soft" />
            <Sun className="relative h-6 w-6 text-accent-gold drop-shadow-[0_0_10px_rgba(233,196,106,0.8)]" />
          </motion.div>
          <div>
            <h1
              className="text-3xl font-semibold tracking-[0.08em]"
              style={{ fontFamily: "'Cinzel', 'Cormorant Garamond', serif" }}
            >
              <span className="accent-text">ORACLE</span>
              <span className="text-text ml-2 font-serif italic text-[22px]">of Olympus</span>
            </h1>
            <div className="laurel-rule mt-1.5 w-[420px] max-w-full" />
            <p className="mt-1.5 text-[10px] text-text-dim font-mono tracking-[0.2em] uppercase">
              Daily · 4H · 15M &nbsp;·&nbsp; Dow × Ichimoku × SMA × Claude Confluence
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 text-[11px]">
          <Stat label="Pantheon" sublabel="監視ペア" value={`${signals.length}`} />
          <Stat
            label="Oracle"
            sublabel="託宣中"
            value={`${alertCount}`}
            highlight={alertCount > 0}
            icon={<Zap className="h-3 w-3" />}
          />
          <Stat label="Threshold" sublabel="閾値" value={config?.alert_threshold ?? "—"} />
          <div
            className={cn(
              "flex flex-col items-end px-3 py-1.5 rounded-lg border",
              freshnessTone === "fresh" && "border-accent-green/40 bg-accent-green/10",
              freshnessTone === "ok" && "border-accent-gold/40 bg-accent-gold/10",
              freshnessTone === "stale" && "border-accent-red/40 bg-accent-red/10",
            )}
          >
            <span className="flex items-center gap-1 text-[9px] uppercase tracking-[0.18em] text-accent-gold/80 font-serif">
              <span
                className={cn(
                  "h-1.5 w-1.5 rounded-full",
                  freshnessTone === "fresh" && "bg-accent-green animate-pulse",
                  freshnessTone === "ok" && "bg-accent-gold",
                  freshnessTone === "stale" && "bg-accent-red animate-pulse",
                )}
              />
              Auspicium
            </span>
            <span className="font-mono text-sm font-semibold">
              {loading ? "取得中…" : formatTime(updatedAt)}
            </span>
          </div>

          {/* Sound toggle */}
          <button
            onClick={toggleSound}
            title={soundEnabled ? "アラート音 ON (クリックで OFF)" : "アラート音 OFF (クリックで ON)"}
            className={cn(
              "h-9 w-9 flex items-center justify-center rounded-lg border transition",
              soundEnabled
                ? "border-accent-gold/50 bg-accent-gold/10 text-accent-gold"
                : "border-border/60 bg-bg-soft/50 text-text-faint hover:text-accent-gold",
            )}
          >
            {soundEnabled ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
          </button>

          {/* Keyboard help */}
          <button
            onClick={() => setShowShortcuts((v) => !v)}
            title="キーボードショートカット"
            className="h-9 w-9 flex items-center justify-center rounded-lg border border-border/60 bg-bg-soft/50 text-text-faint hover:text-text transition"
          >
            <Keyboard className="h-4 w-4" />
          </button>
        </div>
      </div>

      {showShortcuts && (
        <div className="mt-3 p-3 rounded-xl glass border border-border/60 text-[11px] font-mono grid grid-cols-2 md:grid-cols-4 gap-2">
          <ShortcutRow k="1 – 5" v="手法タブ切替" />
          <ShortcutRow k="/" v="ペア検索フォーカス" />
          <ShortcutRow k="R" v="手動リフレッシュ" />
          <ShortcutRow k="Esc" v="詳細/ヘルプを閉じる" />
          <ShortcutRow k="A" v="アラートフィルタ切替" />
          <ShortcutRow k="L / S" v="LONG / SHORT フィルタ" />
          <ShortcutRow k="P" v="ピン止めフィルタ" />
          <ShortcutRow k="M" v="音 ON/OFF" />
        </div>
      )}
    </header>
  );
}

function ShortcutRow({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center gap-2">
      <kbd className="px-1.5 py-0.5 rounded border border-border/60 bg-bg-card text-[10px] text-accent-cyan">
        {k}
      </kbd>
      <span className="text-text-dim">{v}</span>
    </div>
  );
}

function Stat({
  label,
  sublabel,
  value,
  highlight,
  icon,
}: {
  label: string;
  sublabel?: string;
  value: React.ReactNode;
  highlight?: boolean;
  icon?: React.ReactNode;
}) {
  return (
    <div
      className={
        "flex flex-col items-end px-3 py-1.5 rounded-lg border " +
        (highlight
          ? "border-accent-gold/50 bg-accent-gold/10 shadow-[0_0_20px_-8px_rgba(233,196,106,0.6)]"
          : "border-border/50 bg-bg-soft/50")
      }
    >
      <span className="flex items-center gap-1 text-[9px] uppercase tracking-[0.18em] text-accent-gold/80 font-serif">
        {icon}
        {label}
      </span>
      {sublabel && (
        <span className="text-[8px] text-text-faint tracking-widest">{sublabel}</span>
      )}
      <span className="font-mono text-sm font-semibold text-accent-ivory">{value}</span>
    </div>
  );
}
