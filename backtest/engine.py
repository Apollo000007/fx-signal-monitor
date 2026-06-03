"""Backtest engine. Walks historical bars and simulates trades.

設計:
  既存の `strategy.analyze_pair*` を時系列スライスして呼び出すことで、
  ロジック本体を 1 行も変更せず過去のシグナル発火を再現する。

トレード成立ルール:
  - エントリー: is_alert=True の次のバー始値で約定
  - 決済    : SL/TP のうち先に到達した方で約定 (15M バーの OHLC で判定)
              同一バーで両方ヒットした場合は SL 優先 (保守的)
  - 重複    : 同一ペアに open 中のポジションがあれば新規シグナル無視
  - 強制決済: バックテスト終了時点で open のものは終値で決済 + flag

スプレッド/手数料: JPY クロス 1.0 pip、その他 0.5 pip を往復差し引き
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# repo root を import path に追加
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from strategy import analyze_pair  # ORZ
from strategy_pdhl import analyze_pair_pdhl
from strategy_claude import analyze_pair_claude
from strategy_dtp import analyze_pair_dtp
from strategy_pa import analyze_pair_pa
import risk


# UI/運用で使う手法のみ。claude/both は単独では使わないが、
# triple の内部計算 (_get_signal_dict 内) では claude を参照するため
# _get_signal_dict のロジック分岐自体は残してある。
METHOD_NAMES = ("orz", "pdhl", "triple", "dtp", "pa")


def is_jpy_cross(pair: str) -> bool:
    return "/JPY" in pair or "JPY=" in pair


def pip_size(pair: str) -> float:
    return 0.01 if is_jpy_cross(pair) else 0.0001


def spread_pips(pair: str) -> float:
    """概算スプレッド (pips)。バックテスト時に往復で差し引き"""
    return 1.0 if is_jpy_cross(pair) else 0.5


@dataclass
class Trade:
    pair: str
    method: str
    direction: str           # "long" / "short"
    entry_type: str
    entry_time: str
    entry_price: float
    stop_loss: float
    take_profit: float
    score: int
    pattern: Optional[str] = None        # PA 手法: 発火したパターンキー
    exit_time: Optional[str] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None    # "sl" / "tp" / "forced"
    pnl_pips: Optional[float] = None
    pnl_r: Optional[float] = None        # R-multiple (PnL / risk)
    bars_held: Optional[int] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BacktestResult:
    pair: str
    method: str
    period: str
    trades: list[Trade] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "pair": self.pair,
            "method": self.method,
            "period": self.period,
            "trades": [t.to_dict() for t in self.trades],
            "elapsed_seconds": self.elapsed_seconds,
        }


# ---------------- シグナル取得ヘルパ ----------------

def _get_signal_dict(
    method: str,
    pair: str,
    symbol: str,
    df_long_sub: pd.DataFrame,
    df_mid_sub: pd.DataFrame,
    df_h1_sub: Optional[pd.DataFrame],
    df_short_sub: pd.DataFrame,
    threshold: int,
) -> Optional[dict]:
    """指定手法のシグナルを dict 形式で返す。

    各 strategy が異なる戻り型なので、ここで共通形式 dict に正規化。
    キー: direction, price, stop_loss, take_profit, score, is_alert,
          has_trigger, entry_type
    """
    if method == "orz":
        try:
            sig = analyze_pair(pair, symbol, df_long_sub, df_mid_sub, df_short_sub)
        except Exception:
            return None
        if sig.direction == "none":
            return None
        has_trigger = any(r.startswith("★") for r in sig.reasons)
        is_alert = has_trigger and sig.score >= threshold
        return {
            "direction": sig.direction,
            "price": sig.price,
            "stop_loss": sig.stop_loss,
            "take_profit": sig.take_profit,
            "score": sig.score,
            "has_trigger": has_trigger,
            "is_alert": is_alert,
            "entry_type": sig.entry_type,
        }

    if method == "pdhl":
        try:
            d = analyze_pair_pdhl(pair, symbol, df_long_sub, df_mid_sub, df_short_sub,
                                  alert_threshold=threshold)
        except Exception:
            return None
        if d["direction"] == "none":
            return None
        return d

    if method == "claude":
        try:
            d = analyze_pair_claude(pair, symbol, df_long_sub, df_mid_sub, df_short_sub,
                                     alert_threshold=threshold)
        except Exception:
            return None
        if d["direction"] == "none":
            return None
        return d

    if method == "dtp":
        try:
            d = analyze_pair_dtp(pair, symbol, df_long_sub, df_mid_sub, df_short_sub,
                                  alert_threshold=threshold)
        except Exception:
            return None
        if d["direction"] == "none":
            return None
        return d

    if method == "pa":
        try:
            d = analyze_pair_pa(pair, symbol, df_long_sub, df_mid_sub, df_short_sub,
                                alert_threshold=threshold)
        except Exception:
            return None
        if d["direction"] == "none" or d.get("stop_loss") is None:
            return None
        return d

    # ===== 合成手法 (both / triple) =====
    orz = _get_signal_dict("orz", pair, symbol, df_long_sub, df_mid_sub, df_h1_sub, df_short_sub, threshold)
    pdhl = _get_signal_dict("pdhl", pair, symbol, df_long_sub, df_mid_sub, df_h1_sub, df_short_sub, threshold)

    if method == "both":
        if not orz or not pdhl:
            return None
        if orz["direction"] != pdhl["direction"]:
            return None
        # 両方 alert で初めて合意 alert
        return {
            "direction": orz["direction"],
            "price": orz["price"],
            "stop_loss": _tighter_sl(orz["stop_loss"], pdhl["stop_loss"], orz["direction"]),
            "take_profit": _tighter_tp(orz["take_profit"], pdhl["take_profit"], orz["direction"]),
            "score": (orz["score"] + pdhl["score"]) // 2,
            "has_trigger": orz["has_trigger"] and pdhl["has_trigger"],
            "is_alert": orz["is_alert"] and pdhl["is_alert"],
            "entry_type": "both_confluence",
        }

    if method == "triple":
        claude = _get_signal_dict("claude", pair, symbol, df_long_sub, df_mid_sub, df_h1_sub, df_short_sub, threshold)
        if not orz or not pdhl or not claude:
            return None
        if not (orz["direction"] == pdhl["direction"] == claude["direction"]):
            return None
        return {
            "direction": orz["direction"],
            "price": orz["price"],
            "stop_loss": _tighter_sl_n([orz["stop_loss"], pdhl["stop_loss"], claude["stop_loss"]], orz["direction"]),
            "take_profit": _tighter_tp_n([orz["take_profit"], pdhl["take_profit"], claude["take_profit"]], orz["direction"]),
            "score": (orz["score"] + pdhl["score"] + claude["score"]) // 3,
            "has_trigger": orz["has_trigger"] and pdhl["has_trigger"] and claude["has_trigger"],
            "is_alert": orz["is_alert"] and pdhl["is_alert"] and claude["is_alert"],
            "entry_type": "triple_confluence",
        }

    return None


def _tighter_sl(a, b, direction):
    vals = [v for v in (a, b) if v is not None]
    if not vals:
        return None
    return max(vals) if direction == "long" else min(vals)


def _tighter_tp(a, b, direction):
    vals = [v for v in (a, b) if v is not None]
    if not vals:
        return None
    return min(vals) if direction == "long" else max(vals)


def _tighter_sl_n(vals, direction):
    xs = [v for v in vals if v is not None]
    if not xs:
        return None
    return max(xs) if direction == "long" else min(xs)


def _tighter_tp_n(vals, direction):
    xs = [v for v in vals if v is not None]
    if not xs:
        return None
    return min(xs) if direction == "long" else max(xs)


# ---------------- バックテスト本体 ----------------

def run_backtest(
    pair: str,
    symbol: str,
    method: str,
    df_long: pd.DataFrame,
    df_mid: pd.DataFrame,
    df_h1: Optional[pd.DataFrame],
    df_short: pd.DataFrame,
    *,
    threshold: int = 75,
    sample_step: int = 4,
    min_bars: int = 200,
    verbose: bool = False,
    tp_rr: Optional[float] = None,
    min_rr: Optional[float] = 2.0,
) -> BacktestResult:
    """1 ペア × 1 手法のバックテスト。

    sample_step: 15M バーの何本ごとに評価するか (4 = 1 時間に 1 回)。
                 1 にすれば全 15M バーで評価 (最も精密だが遅い)。
    min_bars   : これより前の 15M バーはウォームアップ扱いで評価しない。
    tp_rr      : 数値 (例 3.0) なら TP を entry ± rr*(entry-SL) で固定上書き。
    min_rr     : tp_rr 未指定時に適用する「最低 RR 床」(既定 2.0)。本番 api と
                 同じく利益側で max(構造TP, min_rr×R) に引き上げる → backtest=本番。
                 None で床なし (旧来の生 TP)。
    """
    started = time.monotonic()
    result = BacktestResult(pair=pair, method=method, period=f"{df_short.index[0]}~{df_short.index[-1]}")

    open_trade: Optional[Trade] = None
    open_idx: Optional[int] = None
    pip = pip_size(pair)
    sp = spread_pips(pair) * pip  # スプレッド (price 単位)

    n = len(df_short)
    last_eval_idx = -1

    for i in range(min_bars, n):
        ts = df_short.index[i]

        # ========== 1. 既存ポジションの決済判定 ==========
        if open_trade is not None:
            bar = df_short.iloc[i]
            sl_hit = (
                (open_trade.direction == "long" and bar["Low"] <= open_trade.stop_loss) or
                (open_trade.direction == "short" and bar["High"] >= open_trade.stop_loss)
            )
            tp_hit = (
                (open_trade.direction == "long" and bar["High"] >= open_trade.take_profit) or
                (open_trade.direction == "short" and bar["Low"] <= open_trade.take_profit)
            )

            if sl_hit and tp_hit:
                # 同一バーで両方ヒット → 保守的に SL 採用
                _close_trade(open_trade, ts, open_trade.stop_loss, "sl_tp_ambiguous", i - open_idx, pip, sp)
                result.trades.append(open_trade)
                open_trade = None
            elif sl_hit:
                _close_trade(open_trade, ts, open_trade.stop_loss, "sl", i - open_idx, pip, sp)
                result.trades.append(open_trade)
                open_trade = None
            elif tp_hit:
                _close_trade(open_trade, ts, open_trade.take_profit, "tp", i - open_idx, pip, sp)
                result.trades.append(open_trade)
                open_trade = None

        # ========== 2. 新規シグナル判定 (sample_step ごと) ==========
        if open_trade is None and (i - last_eval_idx) >= sample_step:
            last_eval_idx = i

            # df を時刻 ts まで切り取って analyze_pair に渡す
            df_long_sub = df_long.loc[:ts]
            df_mid_sub = df_mid.loc[:ts]
            df_h1_sub = df_h1.loc[:ts] if df_h1 is not None else None
            df_short_sub = df_short.iloc[:i + 1]

            if len(df_long_sub) < 100 or len(df_mid_sub) < 100:
                continue

            sig = _get_signal_dict(
                method, pair, symbol,
                df_long_sub, df_mid_sub, df_h1_sub, df_short_sub,
                threshold,
            )

            if sig and sig.get("is_alert") and sig.get("stop_loss") and sig.get("take_profit"):
                # 次のバー始値でエントリー
                if i + 1 >= n:
                    continue  # 残バーが無い
                next_bar = df_short.iloc[i + 1]
                entry = float(next_bar["Open"])
                sl = float(sig["stop_loss"])
                tp = float(sig["take_profit"])

                # ★ tp_rr が指定されていれば TP を R-multiple 由来で固定上書き
                #   (entry ± rr × |entry - SL|)
                if tp_rr is not None and tp_rr > 0:
                    r = abs(entry - sl)
                    if r > 0:
                        if sig["direction"] == "long":
                            tp = entry + tp_rr * r
                        elif sig["direction"] == "short":
                            tp = entry - tp_rr * r
                # ★ それ以外は本番と同じ「最低 min_rr 床」を TP に適用
                elif min_rr is not None and min_rr > 0:
                    tp = risk.min_rr_tp(entry, sl, tp, sig["direction"], min_rr)

                # sanity check: direction と SL/TP が整合
                if sig["direction"] == "long" and not (sl < entry < tp):
                    continue
                if sig["direction"] == "short" and not (tp < entry < sl):
                    continue

                open_trade = Trade(
                    pair=pair,
                    method=method,
                    direction=sig["direction"],
                    entry_type=sig.get("entry_type", "—"),
                    entry_time=str(df_short.index[i + 1]),
                    entry_price=entry,
                    stop_loss=sl,
                    take_profit=tp,
                    score=int(sig.get("score", 0)),
                    pattern=sig.get("pattern"),
                )
                open_idx = i + 1
                if verbose:
                    print(f"  [open] {open_trade.entry_time} {open_trade.direction} @ {entry:.5f} "
                          f"SL={sl:.5f} TP={tp:.5f}")

    # ========== 3. 末尾の open は終値で強制決済 ==========
    if open_trade is not None:
        last_bar = df_short.iloc[-1]
        _close_trade(open_trade, df_short.index[-1], float(last_bar["Close"]), "forced", n - 1 - open_idx, pip, sp)
        result.trades.append(open_trade)

    result.elapsed_seconds = time.monotonic() - started
    return result


def _close_trade(trade: Trade, exit_ts, exit_price: float, reason: str, bars_held: int,
                  pip: float, spread: float):
    """Trade を close 状態に更新。スプレッド差し引き済み価格で記録。"""
    # スプレッドを往復で差し引き (long なら exit を下方向、short なら上方向)
    if trade.direction == "long":
        eff_exit = exit_price - spread
        pnl_price = eff_exit - trade.entry_price
        risk_price = trade.entry_price - trade.stop_loss
    else:
        eff_exit = exit_price + spread
        pnl_price = trade.entry_price - eff_exit
        risk_price = trade.stop_loss - trade.entry_price

    trade.exit_time = str(exit_ts)
    trade.exit_price = eff_exit
    trade.exit_reason = reason
    trade.pnl_pips = pnl_price / pip
    trade.pnl_r = pnl_price / risk_price if risk_price else 0.0
    trade.bars_held = bars_held
