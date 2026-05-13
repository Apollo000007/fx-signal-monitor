/**
 * 統一ライブ価格プロキシ。
 *
 * 環境変数で複数プロバイダから自動選択 (優先度順):
 *   1. FINNHUB_API_KEY      → Finnhub /quote (60 req/min・無料・本人確認不要)
 *   2. OANDA_API_TOKEN      → OANDA v20 pricing
 *
 * いずれも未設定なら 503。
 *
 * 使い方: GET /api/live-prices?symbols=USDJPY=X,EURUSD=X
 *   - symbols は yfinance 形式 (=X 付き) でカンマ区切り
 *
 * レスポンス:
 *   {
 *     ok: true,
 *     provider: "finnhub" | "oanda",
 *     interval_hint_ms: number,           // 推奨ポーリング間隔 (レート制限ベース)
 *     prices: [{ symbol, bid, ask, mid, time, tradeable, status }, ...],
 *     fetched_at: string,
 *   }
 */

import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

// ---------------- 環境変数 ----------------

const FINNHUB_API_KEY = process.env.FINNHUB_API_KEY;
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

// ---------------- Finnhub プロバイダ ----------------

async function fetchFinnhub(symbols: string[]): Promise<NormalizedPrice[]> {
  // 各シンボルを並列でクエリ (Finnhub /quote は単一シンボルのみ対応)
  const tasks = symbols.map(async (sym): Promise<NormalizedPrice | null> => {
    const base = YF_TO_BASE[sym];
    if (!base) return null;
    const fh = `OANDA:${base}`;
    const url = `https://finnhub.io/api/v1/quote?symbol=${encodeURIComponent(fh)}&token=${FINNHUB_API_KEY}`;
    try {
      const res = await fetch(url, { cache: "no-store" });
      if (!res.ok) return null;
      const j = (await res.json()) as {
        c?: number; // current price
        pc?: number; // previous close
        t?: number; // unix ts
      };
      const mid = typeof j.c === "number" && j.c > 0 ? j.c : null;
      // Finnhub /quote は bid/ask 分離を返さない → mid のみ、スプレッドは pip 単位で擬似
      const half = mid != null ? (isJpyCross(sym) ? 0.005 : 0.00005) : 0;
      return {
        symbol: sym,
        bid: mid != null ? mid - half : null,
        ask: mid != null ? mid + half : null,
        mid,
        time: j.t ? new Date(j.t * 1000).toISOString() : new Date().toISOString(),
        tradeable: mid != null,
        status: mid != null ? "tradeable" : "no_data",
      };
    } catch {
      return null;
    }
  });
  const results = await Promise.all(tasks);
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

  // プロバイダ自動選択
  let provider: "finnhub" | "oanda" | null = null;
  if (FINNHUB_API_KEY) provider = "finnhub";
  else if (OANDA_API_TOKEN && OANDA_ACCOUNT_ID) provider = "oanda";

  if (!provider) {
    return NextResponse.json(
      {
        ok: false,
        error:
          "プロバイダ未設定。Vercel Environment Variables に FINNHUB_API_KEY (推奨) または OANDA_API_TOKEN + OANDA_ACCOUNT_ID を設定してください。",
      },
      { status: 503 },
    );
  }

  try {
    const prices =
      provider === "finnhub"
        ? await fetchFinnhub(symbols)
        : await fetchOanda(symbols);

    // 推奨ポーリング間隔: プロバイダのレート制限を考慮
    //   Finnhub free = 60 req/min・15 並列 → 15s 安全マージン
    //   OANDA       = 30 req/sec・1 まとめ → 3s
    const intervalHintMs = provider === "finnhub" ? 15000 : 3000;

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
