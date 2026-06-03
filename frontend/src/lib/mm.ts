/**
 * 資産管理 (Money-Management) リスクリワード計算。
 *
 * 設計方針:
 *   - 損切り (SL) は戦略の構造 SL をそのまま採用 → これが 1R (1 単位リスク)。
 *   - 利確 (TP) は R の倍数で決める。最低 2R、推奨 3R。
 *       RR 2 → 損益分岐 勝率 33%、RR 3 → 同 25%。
 *       低勝率でも資産が残る「利益を伸ばす」プロ標準のレシオ。
 *   - 構造的 TP が 2R より遠い場合はそれを活かす (良い目標を潰さない)。
 *     2R より近い (≒ 1:1) 場合は 2R まで引き上げる。
 *
 * 注意: ここはあくまで「表示・通知の目安」計算。strategy*.py / api.py の
 * シグナル本体 (アラート判定・バックテスト・TRIPLE) は一切変更しない。
 */

export interface MMLevels {
  /** 1R = |entry - SL| */
  r: number;
  /** 最低基準 (RR 2) */
  tp2R: number;
  /** 推奨 (RR 3) */
  tp3R: number;
  /** 主利確 = 構造TPと2Rのうち利益側に遠い方 (最低でも 2R を保証) */
  primaryTp: number;
  /** primaryTp の実効リスクリワード */
  rr: number;
}

interface MMInput {
  price: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  direction: string;
}

export function computeMMLevels(signal: MMInput): MMLevels | null {
  const { price, stop_loss, take_profit, direction } = signal;
  if (price == null || stop_loss == null || direction === "none") return null;
  const r = Math.abs(price - stop_loss);
  if (!(r > 0)) return null;
  const isLong = direction === "long";
  const tp2R = isLong ? price + 2 * r : price - 2 * r;
  const tp3R = isLong ? price + 3 * r : price - 3 * r;
  let primaryTp = tp2R;
  if (take_profit != null && Number.isFinite(take_profit)) {
    primaryTp = isLong ? Math.max(take_profit, tp2R) : Math.min(take_profit, tp2R);
  }
  const rr = Math.abs(primaryTp - price) / r;
  return { r, tp2R, tp3R, primaryTp, rr };
}
