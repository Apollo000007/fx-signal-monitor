export type Direction = "long" | "short" | "none";
export type EntryType =
  | "pullback"
  | "breakout"
  | "range_reversal"
  | "wait"
  | "pdhl_long_retest"
  | "pdhl_short_retest"
  | "both_confluence"
  | "claude_confluence_long"
  | "claude_confluence_short"
  | "triple_confluence"
  | "none";
export type Regime = "trend_up" | "trend_down" | "range" | "unclear";

/** UI のタブ / 手法選択キー。
 *  - orz    : 既存 ORZ 手法
 *  - pdhl   : 新手法 1 (PDH/PDL ブレイク+リテスト)
 *  - both   : ORZ + PDHL の合意
 *  - claude : 新手法 2 (Claude Confluence)
 *  - triple : ORZ + PDHL + Claude の 3 手法合意
 */
export type Method = "orz" | "pdhl" | "both" | "claude" | "triple";

export interface TimeframeAnalysis {
  direction: string;
  regime?: Regime | string;
  clarity?: number;
  close: number | null;
  sma20: number | null;
  sma50: number | null;
  sma100: number | null;
  slope20?: number | null;
  slope50?: number | null;
  slope100?: number | null;
  cloud_top: number | null;
  cloud_bottom: number | null;
  price_vs_cloud: "above" | "below" | "inside";
  macd_hist: number | null;
  last_swing_high: number | null;
  last_swing_low: number | null;
  resistances: (number | null)[];
  supports: (number | null)[];
  range_top?: number | null;
  range_bottom?: number | null;
}

/** 1 手法分のシグナル。ペアごとに method を切り替えてビューを作る。 */
export interface MethodSignal {
  direction: Direction;
  entry_type?: EntryType;
  score: number;
  price: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  reasons: string[];
  warnings: string[];
  has_trigger: boolean;
  is_alert: boolean;
  /** PDHL method only */
  pdh?: number | null;
  pdl?: number | null;
}

/** バックエンドから返る 1 ペアのレコード。5 手法分を持つ。 */
export interface PairRecord {
  pair: string;
  symbol: string;
  price: number | null;
  /** 前日高値 (全メソッドで共通利用) */
  pdh: number | null;
  /** 前日安値 (全メソッドで共通利用) */
  pdl: number | null;
  lt: TimeframeAnalysis | null;
  mt: TimeframeAnalysis | null;
  st: TimeframeAnalysis | null;
  orz: MethodSignal;
  pdhl: MethodSignal;
  both: MethodSignal;
  claude: MethodSignal;
  triple: MethodSignal;
}

/** UI から見る view-model: Pair レコード + 選択された手法を projection した形。 */
export interface Signal {
  pair: string;
  symbol: string;
  direction: Direction;
  entry_type?: EntryType;
  score: number;
  price: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  reasons: string[];
  warnings: string[];
  lt: TimeframeAnalysis | null;
  mt: TimeframeAnalysis | null;
  st: TimeframeAnalysis | null;
  has_trigger: boolean;
  is_alert: boolean;
  method: Method;
  /** PDHL method only */
  pdh?: number | null;
  pdl?: number | null;
}

export interface SignalsResponse {
  signals: PairRecord[];
  updated_at: string;
  cached: boolean;
  error?: string;
}

export interface ChartPoint {
  time: number;
  open?: number;
  high?: number;
  low?: number;
  close?: number;
  value?: number;
}

export interface ChartResponse {
  symbol: string;
  tf: "long" | "mid" | "short";
  candles: { time: number; open: number; high: number; low: number; close: number }[];
  sma20: { time: number; value: number }[];
  sma50: { time: number; value: number }[];
  sma100: { time: number; value: number }[];
  senkou_a: { time: number; value: number }[];
  senkou_b: { time: number; value: number }[];
}

export interface AppConfig {
  alert_threshold: number;
  refresh_seconds: number;
  long_label: string;
  mid_label: string;
  short_label: string;
  pair_count: number;
}

/** PairRecord と method から Signal (view-model) を作る。
 *  PDH/PDL は手法に依らず常に rec トップレベルから取得する。 */
export function projectSignal(rec: PairRecord, method: Method): Signal {
  const m = rec[method];
  return {
    pair: rec.pair,
    symbol: rec.symbol,
    direction: m.direction,
    entry_type: m.entry_type,
    score: m.score,
    price: m.price ?? rec.price,
    stop_loss: m.stop_loss,
    take_profit: m.take_profit,
    reasons: m.reasons,
    warnings: m.warnings,
    lt: rec.lt,
    mt: rec.mt,
    st: rec.st,
    has_trigger: m.has_trigger,
    is_alert: m.is_alert,
    method,
    pdh: rec.pdh ?? null,
    pdl: rec.pdl ?? null,
  };
}
