"use client";

import { useEffect, useState } from "react";
import { Radio, AlertCircle, Settings } from "lucide-react";
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
};

/**
 * ヘッダー下に表示する「ライブ価格」のステータスバー。
 *   - 未設定 : 設定方法ガイドへ誘導
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
    return (
      <div className={cn("rounded-xl border border-accent-amber/40 bg-accent-amber/10 px-4 py-2.5 text-[12px] flex items-start gap-2.5", isEvaTheme && "eva-frame")}>
        <Settings className="h-4 w-4 text-accent-amber shrink-0 mt-0.5" />
        <div className="flex-1 leading-relaxed">
          <span className="font-semibold text-accent-amber">
            ライブ価格プロバイダ未設定
          </span>
          <span className="text-text-dim ml-2">
            yfinance の遅延データのみ表示中 (15〜20 分遅延)。リアルタイム値動きを取るには
            Vercel の Environment Variables に{" "}
            <code className="px-1 rounded bg-bg-soft/60 font-mono">FINNHUB_API_KEY</code>{" "}
            (推奨・本人確認不要・60req/min) または{" "}
            <code className="px-1 rounded bg-bg-soft/60 font-mono">OANDA_API_TOKEN</code> +{" "}
            <code className="px-1 rounded bg-bg-soft/60 font-mono">OANDA_ACCOUNT_ID</code> を設定してください。
          </span>
          <a
            href="https://finnhub.io/register"
            target="_blank"
            rel="noopener noreferrer"
            className="ml-2 text-accent-cyan underline"
          >
            Finnhub 無料登録
          </a>
        </div>
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
