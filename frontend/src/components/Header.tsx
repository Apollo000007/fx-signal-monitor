"use client";

import { Activity, Zap, Volume2, VolumeX, Keyboard } from "lucide-react";
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
    <header className="mb-6">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3">
          <motion.div
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: "spring", stiffness: 260, damping: 20 }}
            className="h-10 w-10 rounded-xl bg-accent-gradient flex items-center justify-center shadow-glow"
          >
            <Activity className="h-5 w-5 text-white" />
          </motion.div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              <span className="accent-text">FX Signal</span> Monitor
            </h1>
            <p className="text-[11px] text-text-dim font-mono tracking-wider">
              DAILY · 4H · 15M / DOW THEORY × ICHIMOKU × SMA × CLAUDE CONFLUENCE
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 text-[11px]">
          <Stat label="監視ペア" value={`${signals.length}`} />
          <Stat
            label="アラート中"
            value={`${alertCount}`}
            highlight={alertCount > 0}
            icon={<Zap className="h-3 w-3" />}
          />
          <Stat label="閾値" value={config?.alert_threshold ?? "—"} />
          <div
            className={cn(
              "flex flex-col items-end px-3 py-1.5 rounded-lg border",
              freshnessTone === "fresh" && "border-accent-green/40 bg-accent-green/10",
              freshnessTone === "ok" && "border-accent-amber/40 bg-accent-amber/10",
              freshnessTone === "stale" && "border-accent-red/40 bg-accent-red/10",
            )}
          >
            <span className="flex items-center gap-1 text-[9px] uppercase tracking-widest text-text-faint">
              <span
                className={cn(
                  "h-1.5 w-1.5 rounded-full",
                  freshnessTone === "fresh" && "bg-accent-green animate-pulse",
                  freshnessTone === "ok" && "bg-accent-amber",
                  freshnessTone === "stale" && "bg-accent-red animate-pulse",
                )}
              />
              更新
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
                ? "border-accent-cyan/50 bg-accent-cyan/10 text-accent-cyan"
                : "border-border/60 bg-bg-soft/50 text-text-faint hover:text-text",
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
  value,
  highlight,
  icon,
}: {
  label: string;
  value: React.ReactNode;
  highlight?: boolean;
  icon?: React.ReactNode;
}) {
  return (
    <div
      className={
        "flex flex-col items-end px-3 py-1.5 rounded-lg border " +
        (highlight
          ? "border-accent-amber/40 bg-accent-amber/10"
          : "border-border/50 bg-bg-soft/50")
      }
    >
      <span className="flex items-center gap-1 text-[9px] uppercase tracking-widest text-text-faint">
        {icon}
        {label}
      </span>
      <span className="font-mono text-sm font-semibold">{value}</span>
    </div>
  );
}
