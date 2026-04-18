import type { AppConfig, ChartResponse, ChartTf, SignalsResponse } from "./types";

/**
 * 静的モード: GitHub Actions で事前ビルドされた JSON をそのまま読みに行く。
 * バックエンド無しで動く → Vercel の無料枠だけで完結する。
 *
 * ローカル開発時は NEXT_PUBLIC_STATIC_MODE を設定しない (またはfalse) にすると
 * 従来通り /api/* 経由で FastAPI バックエンドをプロキシ経由で叩く。
 */
const STATIC_MODE =
  process.env.NEXT_PUBLIC_STATIC_MODE === "true" ||
  process.env.NEXT_PUBLIC_STATIC_MODE === "1";

const STATIC_BASE = process.env.NEXT_PUBLIC_STATIC_BASE ?? "";

function staticUrl(path: string): string {
  // path は "/api/..." 形式で渡されてくる
  return `${STATIC_BASE}${path}`;
}

function sanitizeSymbol(symbol: string): string {
  // build_static.py と同じサニタイズ
  return symbol.replace(/=/g, "_").replace(/\//g, "_").replace(/\\/g, "_");
}

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`${url} → ${res.status}`);
  }
  return (await res.json()) as T;
}

export async function getSignals(refresh = false): Promise<SignalsResponse> {
  if (STATIC_MODE) {
    // 静的 JSON はキャッシュバスターだけ付ける
    const bust = refresh ? `?t=${Date.now()}` : `?t=${Math.floor(Date.now() / 60000)}`;
    return fetchJson<SignalsResponse>(staticUrl(`/api/signals.json${bust}`));
  }
  const q = refresh ? "?refresh=true" : "";
  return fetchJson<SignalsResponse>(`/api/signals${q}`);
}

export async function getChart(
  symbol: string,
  tf: ChartTf = "mid",
): Promise<ChartResponse> {
  if (STATIC_MODE) {
    const fname = `${sanitizeSymbol(symbol)}_${tf}.json`;
    return fetchJson<ChartResponse>(
      staticUrl(`/api/chart/${fname}?t=${Math.floor(Date.now() / 60000)}`),
    );
  }
  return fetchJson<ChartResponse>(
    `/api/chart/${encodeURIComponent(symbol)}?tf=${tf}`,
  );
}

export async function getConfig(): Promise<AppConfig> {
  if (STATIC_MODE) {
    return fetchJson<AppConfig>(staticUrl("/api/config.json"));
  }
  return fetchJson<AppConfig>("/api/config");
}
