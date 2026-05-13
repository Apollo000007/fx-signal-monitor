/**
 * ライブ価格プロキシ。
 *
 * 動作モード:
 *   - OANDA_API_TOKEN + OANDA_ACCOUNT_ID 設定済み
 *       → OANDA v20 pricing API を 3 秒間隔で叩ける真のリアルタイム
 *   - 未設定 (デフォルト)
 *       → notConfigured=true。フロントは静的 signals.json (cron 5分更新) のみ使う
 *
 * Finnhub と Yahoo Finance は datacenter IP 経由で実用にならない (403 / rate limit)
 * ことが本番テストで判明したため削除。
 *
 * 使い方: GET /api/live-prices?symbols=USDJPY=X,EURUSD=X
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
// yfinance 形式 "USDJPY=X" ↔ OANDA "USD_JPY"

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

interface NormalizedPrice {
  symbol: string;
  bid: number | null;
  ask: number | null;
  mid: number | null;
  time: string;
  tradeable: boolean;
  status: string;
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

  // OANDA 未設定なら、エラーにせず prices=[] を返す (UI 側で「静的データのみ」表示)
  if (!(OANDA_API_TOKEN && OANDA_ACCOUNT_ID)) {
    return NextResponse.json(
      {
        ok: true,
        provider: null,
        not_configured: true,
        // 静的 signals.json が 5 分 cron で更新されるので、UI のポーリングも 5 分相当
        interval_hint_ms: 300_000,
        prices: [],
        fetched_at: new Date().toISOString(),
        hint:
          "OANDA 未設定。GitHub Actions が 5 分ごとに更新する静的 signals.json を使用してください。" +
          "リアルタイム化したい場合は OANDA Practice (oanda.com) の API トークンを Vercel env に設定してください。",
      },
      { status: 200, headers: { "Cache-Control": "no-store, max-age=0" } },
    );
  }

  try {
    const prices = await fetchOanda(symbols);
    return NextResponse.json(
      {
        ok: true,
        provider: "oanda" as const,
        interval_hint_ms: 3000,
        prices,
        fetched_at: new Date().toISOString(),
      },
      { status: 200, headers: { "Cache-Control": "no-store, max-age=0" } },
    );
  } catch (e: any) {
    return NextResponse.json(
      {
        ok: false,
        provider: "oanda" as const,
        error: "oanda fetch failed",
        detail: String(e?.message ?? e).slice(0, 250),
      },
      { status: 502 },
    );
  }
}
