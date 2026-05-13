"use client";

import { useEffect, useState } from "react";
import { Radio, AlertCircle, Clock } from "lucide-react";
import type { LiveProvider } from "@/lib/oanda";
import { cn } from "@/lib/utils";
import { isEvaTheme } from "@/lib/visualTheme";

interface Props {
  loading: boolean;
  error: string | null;
  notConfigured: boolean;
  lastFetched: number | null;
  intervalMs: number;
  count: number;
  provider: LiveProvider | null;
}

const PROVIDER_LABEL: Record<LiveProvider, string> = {
  finnhub: "Finnhub tick (OANDA 経由)",
  oanda: "OANDA tick",
  yahoo: "Yahoo Finance (near real-time)",
};

/**
 * ヘッダー下に表示する「ライブ価格」のステータスバー。
 *   - 未設定 : 静的データ (5分 cron) で動いていることを案内
 *   - 接続中 : 緑のラジオ波アイコン + 経過秒数 + ペア数 + プロバイダ名
 *   - エラー : 赤バナー
 */
export function LiveStatus({
  loading,
  error,
  notConfigured,
  lastFetched,
  intervalMs,
  count,
  provider,
}: Props) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(id);
  }, []);

  if (notConfigured) {
    // OANDA 未設定: 静的 JSON (cron 5 分) で運用していることを淡く案内するのみ
    return (
      <div
        className={cn(
          "rounded-xl border border-border/60 bg-bg-soft/40 px-4 py-2 text-[11px] flex items-center gap-2",
          isEvaTheme && "eva-frame",
        )}
      >
        <Clock className="h-4 w-4 text-text-dim" />
        <span className="text-text-dim font-semibold">SCHEDULED</span>
        <span className="text-text-faint">
          GitHub Actions が 5 分ごとに自動更新 (yfinance) · ペア数 {count} ·
          リアルタイム化したい場合は OANDA Practice トークンを Vercel env に追加
        </span>
      </div>
    );
  }

  if (error) {
    return (
      <div className={cn("rounded-xl border border-accent-red/40 bg-accent-red/10 px-4 py-2 text-[12px] flex items-center gap-2", isEvaTheme && "eva-frame")}>
        <AlertCircle className="h-4 w-4 text-accent-red" />
        <span className="text-accent-red font-semibold">ライブ価格エラー</span>
        <span className="text-text-dim truncate">{error}</span>
      </div>
    );
  }

  const sinceMs = lastFetched ? now - lastFetched : null;
  const sinceSec = sinceMs != null ? (sinceMs / 1000).toFixed(1) : "—";
  // 経過時間が想定間隔の 2 倍を超えたら遅延中扱い
  const stale = sinceMs != null && sinceMs > intervalMs * 2;

  return (
    <div
      className={cn(
        "rounded-xl border px-4 py-2 text-[12px] flex items-center gap-3 transition-colors",
        isEvaTheme && "eva-frame",
        stale
          ? "border-accent-amber/40 bg-accent-amber/5"
          : "border-accent-green/40 bg-accent-green/5",
      )}
    >
      <div className="relative flex items-center justify-center">
        <Radio
          className={cn(
            "h-4 w-4",
            stale ? "text-accent-amber" : "text-accent-green",
            !stale && "animate-pulse-soft",
          )}
        />
      </div>
      <div className="flex items-baseline gap-2 flex-wrap">
        <span
          className={cn(
            "font-semibold",
            stale ? "text-accent-amber" : "text-accent-green",
          )}
        >
          LIVE
        </span>
        <span className="text-text-dim">
          {provider ? PROVIDER_LABEL[provider] : "tick"} · {count} ペア ·{" "}
          {(intervalMs / 1000).toFixed(intervalMs < 10000 ? 0 : 0)}秒間隔
        </span>
        <span className="text-text-faint font-mono">
          (最終更新 {sinceSec}s 前)
        </span>
        {loading && (
          <span className="text-accent-cyan text-[10px] font-mono uppercase animate-pulse">
            fetching…
          </span>
        )}
      </div>
    </div>
  );
}
