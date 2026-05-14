"""バックテスト結果の統計計算。

入力: list[Trade] (engine.py の Trade)
出力: Stats dict {trades, wins, losses, win_rate, profit_factor,
                  expectancy_r, max_dd_r, longest_streak_loss, ...}
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Iterable

from .engine import Trade


@dataclass
class Stats:
    trades: int = 0
    wins: int = 0
    losses: int = 0
    breakeven: int = 0
    win_rate: float = 0.0
    avg_win_r: float = 0.0
    avg_loss_r: float = 0.0
    profit_factor: float = 0.0
    expectancy_r: float = 0.0
    total_r: float = 0.0
    max_dd_r: float = 0.0
    max_winstreak: int = 0
    max_lossstreak: int = 0
    sharpe_like: float = 0.0  # mean_r / std_r ※トレード単位の簡易シャープ
    by_direction: dict = field(default_factory=dict)
    breakeven_winrate_needed: float = 0.0  # PF=1 を達成するのに必要な勝率
    is_positive_ev: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def compute_stats(trades: Iterable[Trade]) -> Stats:
    trades = [t for t in trades if t.pnl_r is not None]
    s = Stats()
    s.trades = len(trades)
    if not trades:
        return s

    wins = [t for t in trades if t.pnl_r > 0]
    losses = [t for t in trades if t.pnl_r < 0]
    s.wins = len(wins)
    s.losses = len(losses)
    s.breakeven = s.trades - s.wins - s.losses
    s.win_rate = s.wins / s.trades * 100

    s.avg_win_r = _mean([t.pnl_r for t in wins])
    s.avg_loss_r = _mean([t.pnl_r for t in losses])  # 負の値
    s.total_r = sum(t.pnl_r for t in trades)
    s.expectancy_r = s.total_r / s.trades

    gross_win = sum(t.pnl_r for t in wins)
    gross_loss = -sum(t.pnl_r for t in losses)
    s.profit_factor = gross_win / gross_loss if gross_loss > 0 else float("inf")

    # 最大ドローダウン (R 単位)
    running = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in trades:
        running += t.pnl_r
        peak = max(peak, running)
        dd = peak - running
        max_dd = max(max_dd, dd)
    s.max_dd_r = max_dd

    # 連勝/連敗
    cur_w = cur_l = 0
    for t in trades:
        if t.pnl_r > 0:
            cur_w += 1
            cur_l = 0
        else:
            cur_l += 1
            cur_w = 0
        s.max_winstreak = max(s.max_winstreak, cur_w)
        s.max_lossstreak = max(s.max_lossstreak, cur_l)

    # 簡易シャープ: mean / std
    mean = s.expectancy_r
    if s.trades > 1:
        var = sum((t.pnl_r - mean) ** 2 for t in trades) / (s.trades - 1)
        std = var ** 0.5
        s.sharpe_like = mean / std if std > 0 else 0.0

    # 方向別
    s.by_direction = {
        "long": _direction_stats([t for t in trades if t.direction == "long"]),
        "short": _direction_stats([t for t in trades if t.direction == "short"]),
    }

    # PF=1 ブレークイーブン勝率: WR が必要なライン
    #   gross_win = wins * avg_win_r
    #   gross_loss = losses * |avg_loss_r|
    #   PF = 1 のとき win_rate * avg_win = (1-win_rate) * |avg_loss|
    #   win_rate = |avg_loss| / (avg_win + |avg_loss|)
    if s.avg_win_r > 0 and s.avg_loss_r < 0:
        s.breakeven_winrate_needed = abs(s.avg_loss_r) / (s.avg_win_r + abs(s.avg_loss_r)) * 100

    s.is_positive_ev = s.expectancy_r > 0

    return s


def _direction_stats(trades: list[Trade]) -> dict:
    if not trades:
        return {"n": 0}
    wins = sum(1 for t in trades if t.pnl_r > 0)
    return {
        "n": len(trades),
        "win_rate": wins / len(trades) * 100,
        "expectancy_r": sum(t.pnl_r for t in trades) / len(trades),
    }


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def equity_curve(trades: list[Trade]) -> list[float]:
    """累積 R-multiple の時系列 (entry 順)。"""
    curve = []
    running = 0.0
    for t in trades:
        if t.pnl_r is None:
            continue
        running += t.pnl_r
        curve.append(running)
    return curve
