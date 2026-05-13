/**
 * Live Price クライアント。
 *
 * Vercel serverless route (/api/live-prices) 経由で複数プロバイダ
 * (Finnhub / OANDA) から自動選択でライブ価格を取得する。
 * トークンはサーバ側のみで保持 → ブラウザに漏れない。
 *
 * 使い方:
 *   const { prices, provider, error } = useLivePrices(["USDJPY=X", "EURUSD=X"]);
 *   const ujLive = prices.get("USDJPY=X");
 *   console.log(ujLive?.mid, ujLive?.changePips);
 */

import { useEffect, useRef, useState } from "react";

// ============== シンボルマッピング ==============
// yfinance の "USDJPY=X" 形式 ↔ OANDA の "USD_JPY" 形式

/** yfinance シンボル → OANDA instrument。15 ペアすべて対応。 */
export const YF_TO_OANDA: Record<string, string> = {
  "USDJPY=X": "USD_JPY",
  "EURUSD=X": "EUR_USD",
  "GBPUSD=X": "GBP_USD",
  "AUDUSD=X": "AUD_USD",
  "NZDUSD=X": "NZD_USD",
  "USDCAD=X": "USD_CAD",
  "USDCHF=X": "USD_CHF",
  "EURJPY=X": "EUR_JPY",
  "GBPJPY=X": "GBP_JPY",
  "AUDJPY=X": "AUD_JPY",
  "NZDJPY=X": "NZD_JPY",
  "CADJPY=X": "CAD_JPY",
  "CHFJPY=X": "CHF_JPY",
  "ZARJPY=X": "ZAR_JPY",
  "EURGBP=X": "EUR_GBP",
};

export function yfToOanda(symbol: string): string | null {
  return YF_TO_OANDA[symbol] ?? null;
}

/** OANDA → yfinance への逆引きキャッシュ */
const OANDA_TO_YF = Object.fromEntries(
  Object.entries(YF_TO_OANDA).map(([yf, oa]) => [oa, yf]),
);
export function oandaToYf(instrument: string): string | null {
  return OANDA_TO_YF[instrument] ?? null;
}

/** JPY クロスかどうか (pip サイズ判定用) */
export function isJpyCross(instrument: string): boolean {
  return /_JPY$/.test(instrument) || /JPY=X$/.test(instrument);
}

/** ペアの pip サイズ */
export function pipSize(instrument: string): number {
  return isJpyCross(instrument) ? 0.01 : 0.0001;
}

// ============== 型 ==============

export type LiveProvider = "finnhub" | "oanda" | "yahoo" | "saxo";

export interface LivePrice {
  instrument: string;        // "USD_JPY"
  symbol: string;            // "USDJPY=X" (yfinance 形式)
  bid: number | null;
  ask: number | null;
  mid: number | null;
  time: string;
  tradeable: boolean;
  status: string;
  /** 前回 fetch との中値差 (pips、絶対値ではなく符号付き) */
  changePips: number | null;
  /** 前回 fetch から上がった/下がった/横ばい */
  tick: "up" | "down" | "flat" | "init";
}

interface LivePricesResponse {
  ok: boolean;
  error?: string;
  provider?: LiveProvider | null;
  not_configured?: boolean;
  interval_hint_ms?: number;
  prices?: {
    symbol: string;          // yfinance 形式 (=X 付き)
    bid: number | null;
    ask: number | null;
    mid: number | null;
    time: string;
    tradeable: boolean;
    status: string;
  }[];
  fetched_at?: string;
  hint?: string;
}

export interface LivePricesPayload {
  prices: LivePrice[];
  provider: LiveProvider | null;
  intervalHintMs: number;
  notConfigured: boolean;
}

// ============== フェッチ ==============

/**
 * 任意の symbols (yfinance 形式) のライブ価格を 1 回だけ取得。
 * OANDA が設定されていればそちらから、未設定なら静的データ前提で空配列を返す。
 */
export async function fetchLivePrices(symbols: string[]): Promise<LivePricesPayload> {
  const supported = symbols.filter((s) => YF_TO_OANDA[s]);
  if (supported.length === 0) {
    return { prices: [], provider: null, intervalHintMs: 300_000, notConfigured: true };
  }

  const url = `/api/live-prices?symbols=${supported.join(",")}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    let body: any = null;
    try {
      body = await res.json();
    } catch {
      /* ignore */
    }
    throw new Error(body?.error ?? `live-prices proxy HTTP ${res.status}`);
  }
  const data = (await res.json()) as LivePricesResponse;
  if (!data.ok) {
    throw new Error(data.error ?? "live-prices proxy returned not-ok");
  }

  return {
    provider: data.provider ?? null,
    intervalHintMs: data.interval_hint_ms ?? 300_000,
    notConfigured: data.not_configured === true,
    prices: (data.prices ?? []).map((p) => ({
      symbol: p.symbol,
      instrument: yfToOanda(p.symbol) ?? p.symbol,
      bid: p.bid,
      ask: p.ask,
      mid: p.mid,
      time: p.time,
      tradeable: p.tradeable,
      status: p.status,
      changePips: null,
      tick: "init" as const,
    })),
  };
}

// ============== React フック ==============

interface UseLivePricesOptions {
  /** ポーリング間隔 (ms)。既定 3000 = 3 秒 */
  intervalMs?: number;
  /** false で停止 */
  enabled?: boolean;
}

export interface UseLivePricesResult {
  /** symbol(yfinance 形式) → LivePrice */
  prices: Map<string, LivePrice>;
  error: string | null;
  loading: boolean;
  lastFetched: number | null;
  /** 強制更新 */
  refresh: () => void;
  /** プロバイダ未設定なら true */
  notConfigured: boolean;
  /** サーバ側が判定したプロバイダ。未取得時は null */
  provider: LiveProvider | null;
  /** サーバ推奨ポーリング間隔 (ms) */
  effectiveIntervalMs: number;
}

export function useLivePrices(
  symbols: string[],
  opts: UseLivePricesOptions = {},
): UseLivePricesResult {
  const { intervalMs, enabled = true } = opts;
  const [prices, setPrices] = useState<Map<string, LivePrice>>(new Map());
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [lastFetched, setLastFetched] = useState<number | null>(null);
  const [notConfigured, setNotConfigured] = useState(false);
  const [provider, setProvider] = useState<LiveProvider | null>(null);
  const [effectiveIntervalMs, setEffectiveIntervalMs] = useState<number>(
    intervalMs ?? 15000,
  );

  // 直近価格を ref に持って差分計算
  const prevRef = useRef<Map<string, number>>(new Map());
  const symbolsKey = useMemo2(symbols);

  useEffect(() => {
    if (!enabled || symbols.length === 0) return;
    let aborted = false;
    let timer: number | null = null;

    const tick = async () => {
      try {
        setLoading(true);
        const payload = await fetchLivePrices(symbols);
        if (aborted) return;
        const next = new Map<string, LivePrice>();
        for (const lp of payload.prices) {
          const prev = prevRef.current.get(lp.symbol) ?? null;
          if (lp.mid != null && prev != null) {
            const ps = pipSize(lp.instrument);
            const deltaPips = (lp.mid - prev) / ps;
            lp.changePips = deltaPips;
            lp.tick =
              Math.abs(deltaPips) < 0.05
                ? "flat"
                : deltaPips > 0
                  ? "up"
                  : "down";
          } else {
            lp.tick = "init";
            lp.changePips = null;
          }
          next.set(lp.symbol, lp);
          if (lp.mid != null) prevRef.current.set(lp.symbol, lp.mid);
        }
        setPrices(next);
        setProvider(payload.provider);
        setNotConfigured(payload.notConfigured);
        // ユーザー指定があれば優先、なければサーバ推奨値を反映
        const next_interval = intervalMs ?? payload.intervalHintMs;
        setEffectiveIntervalMs(next_interval);
        setError(null);
        setLastFetched(Date.now());
      } catch (e: any) {
        if (aborted) return;
        const msg = String(e?.message ?? e);
        setError(msg);
      } finally {
        if (!aborted) setLoading(false);
      }
    };

    // 即時 1 回 + 定期実行 (サーバ推奨間隔を採用するため、いったん描画後に再セット)
    tick();
    timer = window.setInterval(tick, effectiveIntervalMs);

    return () => {
      aborted = true;
      if (timer != null) window.clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbolsKey, intervalMs, enabled, effectiveIntervalMs]);

  const refresh = () => {
    // 強制再フェッチ: 次のレンダーで useEffect が走るよう lastFetched を nudge する
    setLastFetched((v) => (v ?? 0) + 1);
  };

  return {
    prices,
    error,
    loading,
    lastFetched,
    refresh,
    notConfigured,
    provider,
    effectiveIntervalMs,
  };
}

// シンボル配列の identity 化 (毎レンダーで新配列でも、内容が同じなら effect を再実行しない)
function useMemo2(arr: string[]): string {
  const ref = useRef<string>("");
  const next = arr.slice().sort().join(",");
  if (ref.current !== next) ref.current = next;
  return ref.current;
}
