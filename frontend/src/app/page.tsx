"use client";

import { AnimatePresence } from "framer-motion";
import { useEffect, useMemo } from "react";
import { DetailDrawer } from "@/components/DetailDrawer";
import { FilterBar } from "@/components/FilterBar";
import { Header } from "@/components/Header";
import { MethodTabs } from "@/components/MethodTabs";
import { SignalCard } from "@/components/SignalCard";
import { ToastStack } from "@/components/ToastStack";
import { selectFilteredSignals, useSignalsStore } from "@/store/signals";

export default function DashboardPage() {
  const store = useSignalsStore();
  const {
    fetchConfig,
    refresh,
    config,
    signals,
    loading,
    error,
    selected,
    setSelected,
    pinned,
    togglePin,
    setMethod,
    setFilter,
    toggleSound,
  } = store;

  // Initial load
  useEffect(() => {
    fetchConfig();
    refresh();
  }, [fetchConfig, refresh]);

  // Auto-refresh loop
  useEffect(() => {
    if (!config) return;
    const ms = Math.max(30, config.refresh_seconds) * 1000;
    const id = setInterval(() => refresh(true), ms);
    return () => clearInterval(id);
  }, [config, refresh]);

  // --- Global keyboard shortcuts ------------------------------------------
  useEffect(() => {
    const methodKeys: Record<string, "orz" | "pdhl" | "both" | "claude" | "triple"> = {
      "1": "orz",
      "2": "pdhl",
      "3": "both",
      "4": "claude",
      "5": "triple",
    };
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const isTyping =
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable);

      // Escape は常に有効 (入力中でも詳細を閉じる)
      if (e.key === "Escape") {
        setSelected(null);
        return;
      }
      if (isTyping) return;

      if (methodKeys[e.key]) {
        setMethod(methodKeys[e.key]);
        return;
      }
      if (e.key === "/") {
        e.preventDefault();
        const el = document.querySelector<HTMLInputElement>("input[data-search]");
        el?.focus();
        return;
      }
      if (e.key === "r" || e.key === "R") {
        refresh(true);
        return;
      }
      if (e.key === "a" || e.key === "A") setFilter("alerts");
      if (e.key === "l" || e.key === "L") setFilter("long");
      if (e.key === "s" || e.key === "S") setFilter("short");
      if (e.key === "p" || e.key === "P") setFilter("pinned");
      if (e.key === "m" || e.key === "M") toggleSound();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setSelected, setMethod, setFilter, refresh, toggleSound]);

  const filtered = useMemo(() => selectFilteredSignals(store), [store]);
  const selectedSignal = useMemo(
    () => signals.find((s) => s.pair === selected) ?? null,
    [signals, selected],
  );
  const threshold = config?.alert_threshold ?? 75;

  return (
    <main className="max-w-[1400px] mx-auto px-6 py-8">
      <Header />

      <div className="mb-4">
        <MethodTabs />
      </div>

      <div className="mb-5">
        <FilterBar />
      </div>

      {error && (
        <div className="mb-4 rounded-xl border border-accent-red/40 bg-accent-red/10 p-3 text-sm text-accent-red">
          エラー: {error}
        </div>
      )}

      {loading && signals.length === 0 && (
        <div className="rounded-2xl glass p-10 flex flex-col items-center gap-3 text-text-dim">
          <div className="relative h-14 w-14">
            <div className="absolute inset-0 rounded-full border-2 border-accent-gold/30 border-t-accent-gold animate-spin" />
            <div className="absolute inset-2 rounded-full border border-accent-violet/30 border-b-accent-violet animate-spin [animation-duration:3s]" />
          </div>
          <p className="text-sm font-serif tracking-widest text-accent-gold">
            神託を伺っています…
          </p>
          <p className="text-[11px] text-text-faint">
            Consulting the Oracle · 初回は15秒ほどかかります
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        <AnimatePresence>
          {filtered.map((s) => (
            <SignalCard
              key={s.pair}
              signal={s}
              pinned={pinned.includes(s.pair)}
              threshold={threshold}
              onSelect={() => setSelected(s.pair)}
              onTogglePin={() => togglePin(s.pair)}
            />
          ))}
        </AnimatePresence>
      </div>

      {filtered.length === 0 && !loading && signals.length > 0 && (
        <div className="rounded-2xl glass p-10 text-center text-text-dim text-sm">
          該当する銘柄がありません。フィルタ条件を変えてみてください。
        </div>
      )}

      <DetailDrawer
        signal={selectedSignal}
        threshold={threshold}
        onClose={() => setSelected(null)}
      />

      <ToastStack />

      <footer className="mt-10 pt-6 relative">
        <div className="divider-golden mb-4" />
        <div className="flex flex-wrap items-center justify-between gap-3 text-[10px] text-text-faint">
          <span className="font-serif italic tracking-wider">
            ΓΝΩΘΙ ΣΑΥΤΟΝ · 汝自身を知れ &nbsp;·&nbsp; Data: Yahoo Finance (delayed)
          </span>
          <span className="font-serif tracking-wider">
            ☀ = 15M トリガー発火中 (神託が降りた瞬間)
          </span>
        </div>
      </footer>
    </main>
  );
}
