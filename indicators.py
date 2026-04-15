"""テクニカル指標モジュール。SMA, EMA, MACD, RSI, ATR, 一目均衡表, スイング点検出。"""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def slope(series: pd.Series, bars: int = 5) -> float:
    """直近 bars 本の間の変化率を % で返す。SMA の傾き判定に使用。

    ORZ 手法では「SMAの角度(傾斜)」を相場判断の要素として重視するため、
    数値化しておく。
    """
    if series is None or len(series) < bars + 1:
        return 0.0
    recent = series.iloc[-1]
    past = series.iloc[-1 - bars]
    if pd.isna(recent) or pd.isna(past) or past == 0:
        return 0.0
    return float((recent - past) / past * 100.0)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """MACDライン / シグナルライン / ヒストグラム を返す。"""
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder 方式に近い RSI (指数移動平均)。"""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average True Range (Wilder 方式)。ボラティリティ計測用。"""
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def ichimoku(high: pd.Series, low: pd.Series):
    """一目均衡表の主要ライン。Tenkan(9), Kijun(26), SenkouA, SenkouB を返す。
    Senkou A/B は 26 期間先行に shift 済み。"""
    tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2
    kijun = (high.rolling(26).max() + low.rolling(26).min()) / 2
    senkou_a = ((tenkan + kijun) / 2).shift(26)
    senkou_b = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)
    return tenkan, kijun, senkou_a, senkou_b


def find_swings(df: pd.DataFrame, window: int = 3):
    """単純なピボットによるスイング高値/安値検出。
    Returns: (swing_highs, swing_lows) 各 [(index, price), ...]"""
    highs = df["High"].values
    lows = df["Low"].values
    swing_highs = []
    swing_lows = []
    n = len(df)
    for i in range(window, n - window):
        h_slice = highs[i - window : i + window + 1]
        l_slice = lows[i - window : i + window + 1]
        if highs[i] == h_slice.max() and np.argmax(h_slice) == window:
            swing_highs.append((i, float(highs[i])))
        if lows[i] == l_slice.min() and np.argmin(l_slice) == window:
            swing_lows.append((i, float(lows[i])))
    return swing_highs, swing_lows


def cluster_levels(levels: list[float], tolerance_pct: float = 0.002) -> list[float]:
    """近い価格レベルを平均してクラスタ化。意識されやすい水平線抽出に使う。"""
    if not levels:
        return []
    sorted_levels = sorted(levels)
    clusters: list[list[float]] = [[sorted_levels[0]]]
    for lv in sorted_levels[1:]:
        if abs(lv - clusters[-1][-1]) / clusters[-1][-1] < tolerance_pct:
            clusters[-1].append(lv)
        else:
            clusters.append([lv])
    # 2回以上タッチしたものをレジサポ候補とし、平均値を代表値に
    return [sum(c) / len(c) for c in clusters if len(c) >= 2]
