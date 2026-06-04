"use client";

import { AnimatePresence } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import { AlertImpactOverlay } from "@/components/AlertImpactOverlay";
import { DetailDrawer } from "@/components/DetailDrawer";
import { EconCalendarDrawer } from "@/components/EconCalendarDrawer";
import { fetchCalendar, type CalendarPayload } from "@/lib/calendar";
import { FilterBar } from "@/components/FilterBar";
import { Header } from "@/components/Header";
import { LiveStatus } from "@/components/LiveStatus";
import { MethodTabs } from "@/components/MethodTabs";
import { PaperStats } from "@/components/PaperStats";
import { SignalCard } from "@/components/SignalCard";
import { TestAlertButton } from "@/components/TestAlertButton";
import { ToastStack } from "@/components/ToastStack";
import { useLivePrices } from "@/lib/oanda";
import { useLiveLevelAlerts } from "@/lib/liveAlerts";
import { isEvaTheme } from "@/lib/visualTheme";
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

  // 経済カレンダー / 当日相場リスク
  const [calendar, setCalendar] = useState<CalendarPayload | null>(null);
  const [showCalendar, setShowCalendar] = useState(false);

  // Initial load
  useEffect(() => {
    fetchConfig();
    refresh();
  }, [fetchConfig, refresh]);

  // 経済カレンダーを取得 (5 分ごと。cron が calendar.json を更新)
  useEffect(() => {
    let alive = true;
    const load = () => fetchCalendar().then((c) => { if (alive) setCalendar(c); });
    load();
    const id = setInterval(load, 5 * 60_000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  // Auto-refresh loop
  useEffect(() => {
    if (!config) return;
    const ms = Math.max(30, config.refresh_seconds) * 1000;
    const id = setInterval(() => refresh(true), ms);
    return () => clearInterval(id);
  }, [config, refresh]);

  // --- Global keyboard shortcuts ------------------------------------------
  useEffect(() => {
    const methodKeys: Record<string, "orz" | "pdhl" | "both" | "claude" | "triple" | "dtp" | "pa" | "mtf"> = {
      "1": "orz",
      "2": "pdhl",
      "3": "both",
      "4": "claude",
      "5": "triple",
      "6": "dtp",
      "7": "pa",
      "8": "mtf",
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
      if (e.key === "n" || e.key === "N") setShowCalendar((v) => !v);
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

  // --- Live prices (Finnhub / OANDA 自動選択) ---
  // 1 分間隔で価格更新。プロバイダ未設定なら notConfigured=true でガイドバナーが出るだけ。
  // (スキャルピング向けに 1 秒〜にする場合は intervalMs を変える)
  const liveSymbols = useMemo(() => signals.map((s) => s.symbol), [signals]);
  const live = useLivePrices(liveSymbols, { intervalMs: 60_000 });

  // ライブ価格がキーレベル (PDH/PDL/Entry/SL/TP) を抜けた瞬間にブラウザ通知 + 音
  useLiveLevelAlerts(signals, live.prices);

  return (
    <main className="max-w-[1400px] mx-auto px-6 py-8">
      <Header
        calendarRisk={calendar?.risk ?? null}
        onOpenCalendar={() => setShowCalendar(true)}
      />

      <div className="mb-4">
        <MethodTabs />
      </div>

      <div className="mb-3">
        <LiveStatus
          loading={live.loading}
          error={live.error}
          notConfigured={live.notConfigured}
          lastFetched={live.lastFetched}
          intervalMs={live.effectiveIntervalMs}
          count={live.prices.size}
          provider={live.provider}
        />
      </div>

      <div className="mb-5">
        <PaperStats />
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
        <div className="rounded-2xl glass eva-frame p-10 flex flex-col items-center gap-3 text-text-dim">
          <div className="relative h-14 w-14">
            <div className="absolute inset-0 rounded-full border-2 border-accent-gold/30 border-t-accent-gold animate-spin" />
            <div className="absolute inset-2 rounded-full border border-accent-violet/30 border-b-accent-violet animate-spin [animation-duration:3s]" />
          </div>
          <p className="text-sm font-serif text-accent-gold">
            {isEvaTheme ? "SIGNAL ARRAY SYNCHRONIZING..." : "神託を伺っています…"}
          </p>
          <p className="text-[11px] text-text-faint">
            {isEvaTheme ? "初回は15秒ほどかかります" : "Consulting the Oracle · 初回は15秒ほどかかります"}
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
              live={live.prices.get(s.symbol) ?? null}
              onSelect={() => setSelected(s.pair)}
              onTogglePin={() => togglePin(s.pair)}
            />
          ))}
        </AnimatePresence>
      </div>

      {filtered.length === 0 && !loading && signals.length > 0 && (
        <div className="rounded-2xl glass eva-frame p-10 text-center text-text-dim text-sm">
          該当する銘柄がありません。フィルタ条件を変えてみてください。
        </div>
      )}

      <DetailDrawer
        signal={selectedSignal}
        threshold={threshold}
        live={selectedSignal ? live.prices.get(selectedSignal.symbol) ?? null : null}
        onClose={() => setSelected(null)}
      />

      <EconCalendarDrawer
        open={showCalendar}
        payload={calendar}
        onClose={() => setShowCalendar(false)}
      />

      <ToastStack />
      <TestAlertButton />
      <AlertImpactOverlay />

      <footer className="mt-10 pt-6 relative">
        <div className="divider-golden mb-4" />
        <div className="flex flex-wrap items-center justify-between gap-3 text-[10px] text-text-faint">
          <span className="font-serif">
            {isEvaTheme
              ? "OPERATION TERMINAL · Data: Yahoo Finance (delayed)"
              : "ΓΝΩΘΙ ΣΑΥΤΟΝ · 汝自身を知れ · Data: Yahoo Finance (delayed)"}
          </span>
          <span className="font-serif">
            {isEvaTheme
              ? "! = 15M トリガー発火中"
              : "☀ = 15M トリガー発火中 (神託が降りた瞬間)"}
          </span>
        </div>
      </footer>
    </main>
  );
}
