/**
 * ライブ価格プロキシ。
 *
 * プロバイダ優先順位 (環境変数で自動選択):
 *   1. OANDA_API_TOKEN + OANDA_ACCOUNT_ID → OANDA v20 pricing (3 秒)
 *   2. SAXO_API_TOKEN                     → Saxo Bank OpenAPI infoprices (3 秒)
 *   3. 未設定                              → not_configured=true で空配列 + ヒント返却
 *
 * 既知の不採用プロバイダ (実本番でダメだったもの):
 *   - Finnhub free tier: forex /quote が HTTP 403
 *   - Yahoo Finance direct: Vercel datacenter IP がレート制限される
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

const SAXO_API_TOKEN = process.env.SAXO_API_TOKEN;
const SAXO_ENV = (process.env.SAXO_ENV ?? "sim").toLowerCase();
const SAXO_BASE =
  SAXO_ENV === "live"
    ? "https://gateway.saxobank.com/openapi"
    : "https://gateway.saxobank.com/sim/openapi";

// ---------------- シンボル変換 ----------------

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

// Saxo Bank の Universal Instrument Code (UIC)。FxSpot 系の主要 15 ペアをハードコード。
// (動的に /ref/v1/instruments で取得することも可能だが、cold start を抑えるため固定値)
const YF_TO_SAXO_UIC: Record<string, number> = {
  "EURUSD=X": 21,
  "USDJPY=X": 42,
  "GBPUSD=X": 31,
  "AUDUSD=X": 5,
  "NZDUSD=X": 37,
  "USDCAD=X": 38,
  "USDCHF=X": 39,
  "EURJPY=X": 18,
  "GBPJPY=X": 26,
  "AUDJPY=X": 2,
  "NZDJPY=X": 36,
  "CADJPY=X": 13,
  "CHFJPY=X": 14,
  "ZARJPY=X": 65,
  "EURGBP=X": 17,
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

// ---------------- Saxo Bank プロバイダ ----------------

async function fetchSaxo(symbols: string[]): Promise<NormalizedPrice[]> {
  // yfinance シンボル → UIC へ。マップに無いものは無視。
  const pairs = symbols
    .map((sym) => ({ sym, uic: YF_TO_SAXO_UIC[sym] }))
    .filter((p): p is { sym: string; uic: number } => p.uic != null);
  if (pairs.length === 0) return [];

  // /trade/v1/infoprices は複数 UIC を 1 リクエストで取れる
  // ※ FieldGroups=Quote を指定しないと bid/ask が返ってこない
  const uicList = pairs.map((p) => p.uic).join(",");
  const url =
    `${SAXO_BASE}/trade/v1/infoprices?Uics=${uicList}&AssetType=FxSpot&FieldGroups=Quote`;
  const res = await fetch(url, {
    headers: {
      Authorization: `Bearer ${SAXO_API_TOKEN}`,
      Accept: "application/json",
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Saxo HTTP ${res.status}: ${text.slice(0, 200)}`);
  }
  const data = (await res.json()) as {
    Data?: {
      Uic: number;
      Quote?: {
        Bid?: number;
        Ask?: number;
        Mid?: number;
      };
      LastUpdated?: string;
      PriceInfoDetails?: { LastTraded?: number };
    }[];
  };
  const uicToYf = new Map(pairs.map((p) => [p.uic, p.sym]));
  return (data.Data ?? [])
    .map((entry): NormalizedPrice | null => {
      const sym = uicToYf.get(entry.Uic);
      if (!sym) return null;
      const bid = entry.Quote?.Bid ?? null;
      const ask = entry.Quote?.Ask ?? null;
      let mid: number | null = entry.Quote?.Mid ?? null;
      if (mid == null && bid != null && ask != null) mid = (bid + ask) / 2;
      if (mid == null) mid = bid ?? ask;
      if (mid == null) return null;
      return {
        symbol: sym,
        bid,
        ask,
        mid,
        time: entry.LastUpdated ?? new Date().toISOString(),
        tradeable: true,
        status: "tradeable",
      };
    })
    .filter((x): x is NormalizedPrice => x != null);
}

// ---------------- ルートハンドラ ----------------

type Provider = "oanda" | "saxo";

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
  let provider: Provider | null = null;
  if (OANDA_API_TOKEN && OANDA_ACCOUNT_ID) provider = "oanda";
  else if (SAXO_API_TOKEN) provider = "saxo";

  if (!provider) {
    return NextResponse.json(
      {
        ok: true,
        provider: null,
        not_configured: true,
        interval_hint_ms: 300_000,
        prices: [],
        fetched_at: new Date().toISOString(),
        hint:
          "リアルタイムプロバイダ未設定。OANDA Practice または Saxo SIM のトークンを Vercel env に設定してください。" +
          "未設定でも 5 分 cron の静的 signals.json は配信されます。",
      },
      { status: 200, headers: { "Cache-Control": "no-store, max-age=0" } },
    );
  }

  try {
    const prices =
      provider === "oanda"
        ? await fetchOanda(symbols)
        : await fetchSaxo(symbols);
    return NextResponse.json(
      {
        ok: true,
        provider,
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
        provider,
        error: `${provider} fetch failed`,
        detail: String(e?.message ?? e).slice(0, 250),
      },
      { status: 502 },
    );
  }
}
