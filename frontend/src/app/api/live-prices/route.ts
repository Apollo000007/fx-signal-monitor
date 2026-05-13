/**
 * 統一ライブ価格プロキシ。
 *
 * 環境変数で複数プロバイダから自動選択 (優先度順):
 *   1. OANDA_API_TOKEN + OANDA_ACCOUNT_ID → OANDA v20 pricing (3 秒間隔可)
 *   2. (fallback)                         → Yahoo Finance public API (認証不要)
 *
 * Yahoo は環境変数不要で誰でも使える。本家 yfinance と同じデータソース。
 * 遅延は 1〜3 分程度だが、yfinance バックエンド (15 分 cron) より大幅高速。
 *
 * 注意: FINNHUB_API_KEY を設定しても無料枠では forex の /quote が 403 を返すため
 * 現在は Finnhub 対応コードを保持するのみで実際には Yahoo にフォールバックする。
 *
 * 使い方: GET /api/live-prices?symbols=USDJPY=X,EURUSD=X
 *   - symbols は yfinance 形式 (=X 付き) でカンマ区切り
 *
 * レスポンス:
 *   {
 *     ok: true,
 *     provider: "oanda" | "yahoo",
 *     interval_hint_ms: number,           // 推奨ポーリング間隔
 *     prices: [{ symbol, bid, ask, mid, time, tradeable, status }, ...],
 *     fetched_at: string,
 *   }
 */

import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

// ---------------- 環境変数 ----------------

const OANDA_API_TOKEN = process.env.OANDA_API_TOKEN;
const OANDA_ACCOUNT_ID = process.env.OANDA_ACCOUNT_ID;
const OANDA_ENV = (process.env.OANDA_ENV ?? "practice").toLowerCase();

const OANDA_BASE =
  OANDA_ENV === "live"
    ? "https://api-fxtrade.oanda.com"
    : "https://api-fxpractice.oanda.com";

// ---------------- シンボル変換 ----------------
// yfinance 形式 "USDJPY=X" を各プロバイダ形式に。
//   OANDA   : "USD_JPY"
//   Finnhub : "OANDA:USD_JPY"  (Finnhub は OANDA を裏で再配信)

const YF_TO_BASE: Record<string, string> = {
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

function isJpyCross(symbol: string): boolean {
  return /JPY=X$/.test(symbol) || /_JPY$/.test(symbol);
}

interface NormalizedPrice {
  symbol: string;
  bid: number | null;
  ask: number | null;
  mid: number | null;
  time: string;
  tradeable: boolean;
  status: string;
}

// ---------------- Yahoo Finance プロバイダ (デフォルト・認証不要) ----------------
//
// Yahoo Finance の public chart API は API key 無しで叩け、yfinance Python
// ライブラリと同じデータソース。日中のメジャー FX ペアは数秒〜数十秒遅延で
// 取得可能 (公式の保証は無いが安定して動作している。)
//
// エンドポイント:
//   GET https://query1.finance.yahoo.com/v8/finance/chart/USDJPY=X?interval=1m&range=1d
//
// レスポンス meta.regularMarketPrice / regularMarketTime が最新値。

interface YahooChart {
  chart?: {
    result?: {
      meta?: {
        regularMarketPrice?: number;
        regularMarketTime?: number;
        symbol?: string;
      };
    }[];
    error?: { code: string; description: string } | null;
  };
}

async function fetchYahooOne(symbol: string): Promise<NormalizedPrice | null> {
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?interval=1m&range=1d&includePrePost=false`;
  try {
    const res = await fetch(url, {
      cache: "no-store",
      headers: {
        // Yahoo は UA 無しだと 401 を返すことがある
        "User-Agent":
          "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
      },
    });
    if (!res.ok) return null;
    const j = (await res.json()) as YahooChart;
    const meta = j.chart?.result?.[0]?.meta;
    const mid = meta?.regularMarketPrice;
    const t = meta?.regularMarketTime;
    if (typeof mid !== "number" || mid <= 0) return null;
    // Yahoo は bid/ask 別を chart API では返さないので mid から擬似スプレッド
    const half = isJpyCross(symbol) ? 0.005 : 0.00005;
    return {
      symbol,
      bid: mid - half,
      ask: mid + half,
      mid,
      time: t ? new Date(t * 1000).toISOString() : new Date().toISOString(),
      tradeable: true,
      status: "tradeable",
    };
  } catch {
    return null;
  }
}

async function fetchYahoo(symbols: string[]): Promise<NormalizedPrice[]> {
  const valid = symbols.filter((s) => YF_TO_BASE[s]);
  const results = await Promise.all(valid.map((s) => fetchYahooOne(s)));
  return results.filter((x): x is NormalizedPrice => x != null);
}

// ---------------- OANDA プロバイダ ----------------

async function fetchOanda(symbols: string[]): Promise<NormalizedPrice[]> {
  const instruments = symbols
    .map((s) => YF_TO_BASE[s])
    .filter((x): x is string => !!x)
    .join(",");
  if (!instruments) return [];
  const url = `${OANDA_BASE}/v3/accounts/${OANDA_ACCOUNT_ID}/pricing?instruments=${instruments}`;
  const res = await fetch(url, {
    headers: {
      Authorization: `Bearer ${OANDA_API_TOKEN}`,
      "Accept-Datetime-Format": "RFC3339",
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`OANDA HTTP ${res.status}: ${text.slice(0, 200)}`);
  }
  const data = (await res.json()) as {
    prices?: {
      instrument: string;
      time: string;
      bids?: { price: string }[];
      asks?: { price: string }[];
      status?: string;
      tradeable?: boolean;
    }[];
  };
  // OANDA は base 形式 (USD_JPY) を返してくる → yfinance 形式に逆変換
  const baseToYf = new Map(Object.entries(YF_TO_BASE).map(([yf, base]) => [base, yf]));
  return (data.prices ?? []).map((p) => {
    const bid = p.bids?.[0]?.price ? Number(p.bids[0].price) : null;
    const ask = p.asks?.[0]?.price ? Number(p.asks[0].price) : null;
    const mid = bid != null && ask != null ? (bid + ask) / 2 : (bid ?? ask);
    return {
      symbol: baseToYf.get(p.instrument) ?? p.instrument,
      bid,
      ask,
      mid,
      time: p.time,
      tradeable: p.tradeable ?? p.status === "tradeable",
      status: p.status ?? "unknown",
    };
  });
}

// ---------------- ルートハンドラ ----------------

export async function GET(req: NextRequest) {
  const symbolsParam = req.nextUrl.searchParams.get("symbols");
  if (!symbolsParam) {
    return NextResponse.json(
      { ok: false, error: "symbols クエリ必須 (yfinance 形式、例: USDJPY=X,EURUSD=X)" },
      { status: 400 },
    );
  }
  const symbols = symbolsParam
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

  // プロバイダ自動選択:
  //   OANDA が設定済みなら 3 秒間隔で OANDA、なければ Yahoo Finance (認証不要)
  //   ※ Finnhub 無料枠は forex の /quote が 403 なので使わない
  const provider: "oanda" | "yahoo" =
    OANDA_API_TOKEN && OANDA_ACCOUNT_ID ? "oanda" : "yahoo";

  try {
    const prices =
      provider === "oanda"
        ? await fetchOanda(symbols)
        : await fetchYahoo(symbols);

    // 推奨ポーリング間隔:
    //   OANDA = 30 req/sec・1 まとめ → 3s
    //   Yahoo = 15 並列を毎分 → 60s が無難 (Yahoo は厳しいレート制限なし)
    const intervalHintMs = provider === "oanda" ? 3000 : 60000;

    return NextResponse.json(
      {
        ok: true,
        provider,
        interval_hint_ms: intervalHintMs,
        prices,
        fetched_at: new Date().toISOString(),
      },
      {
        status: 200,
        headers: { "Cache-Control": "no-store, max-age=0" },
      },
    );
  } catch (e: any) {
    return NextResponse.json(
      {
        ok: false,
        provider,
        error: `${provider} fetch failed`,
        detail: String(e?.message ?? e),
      },
      { status: 502 },
    );
  }
}
