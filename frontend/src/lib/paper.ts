/**
 * Paper Trade 統計の型定義 + フェッチ関数。
 *
 * cron が `frontend/public/api/paper.json` を書き出すので、
 * フロントは静的にそれを fetch する (Vercel 配信なので CDN キャッシュ済み)。
 */

export interface PaperPosition {
  id: string;
  pair: string;
  method: string;
  direction: "long" | "short";
  entry_type: string;
  entry_time: string;
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  score: number;
  last_check_time?: string;
}

export interface PaperTrade {
  id: string;
  pair: string;
  method: string;
  direction: "long" | "short";
  entry_type: string;
  entry_time: string;
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  score: number;
  exit_time: string;
  exit_price: number;
  exit_reason: "sl" | "tp" | "sl_tp_ambiguous";
  pnl_pips: number;
  pnl_r: number;
}

export interface PaperMethodStats {
  trades: number;
  wins: number;
  win_rate: number;
  total_r: number;
  expectancy_r: number;
}

export interface PaperStats {
  trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  total_r: number;
  expectancy_r: number;
  profit_factor: number;
  by_method: Record<string, PaperMethodStats>;
}

export interface PaperPayload {
  updated_at: string;
  open_count: number;
  open_positions: PaperPosition[];
  history_count: number;
  recent_trades: PaperTrade[];
  stats: PaperStats;
}

export async function fetchPaper(): Promise<PaperPayload | null> {
  try {
    const res = await fetch(`/api/paper.json?t=${Math.floor(Date.now() / 60000)}`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as PaperPayload;
  } catch {
    return null;
  }
}
