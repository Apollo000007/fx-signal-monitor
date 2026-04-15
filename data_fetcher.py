"""yfinance を使って複数通貨ペア・複数時間軸の OHLC を取得。

yfinance は 4h を直接サポートしないため、1h を取ってから 4h に
リサンプリングする方式を使う（resample 引数）。
"""
from __future__ import annotations

import pandas as pd
import yfinance as yf


REQUIRED_COLS = ["Open", "High", "Low", "Close"]

_RESAMPLE_AGG = {
    "Open": "first",
    "High": "max",
    "Low": "min",
    "Close": "last",
}


def _extract_single(df: pd.DataFrame, symbol: str) -> pd.DataFrame | None:
    """yf.download の結果から 1 銘柄分を取り出して正規化。"""
    try:
        if isinstance(df.columns, pd.MultiIndex):
            if symbol in df.columns.get_level_values(0):
                sub = df[symbol].copy()
            else:
                return None
        else:
            sub = df.copy()
        sub = sub[[c for c in REQUIRED_COLS if c in sub.columns]].dropna()
        if sub.empty:
            return None
        return sub
    except Exception:
        return None


def _resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """OHLC を任意の時間軸に集約（4h など）。"""
    if df is None or df.empty:
        return df
    try:
        out = df.resample(rule).agg(_RESAMPLE_AGG).dropna()
        return out
    except Exception as e:
        print(f"[data_fetcher] resample error ({rule}): {e}")
        return df


def fetch_multi(
    symbols: list[str],
    interval: str,
    period: str,
    resample: str | None = None,
) -> dict:
    """複数銘柄を 1 回のリクエストで取得して {symbol: DataFrame} を返す。
    resample を指定すると OHLC 集約して返す（例: "4h"）。"""
    if not symbols:
        return {}
    tickers_str = " ".join(symbols)
    try:
        data = yf.download(
            tickers_str,
            interval=interval,
            period=period,
            group_by="ticker",
            threads=True,
            progress=False,
            auto_adjust=False,
        )
    except Exception as e:
        print(f"[data_fetcher] fetch error ({interval}/{period}): {e}")
        return {s: None for s in symbols}

    result: dict = {}
    if len(symbols) == 1:
        df = _extract_single(data, symbols[0])
        if df is not None and resample:
            df = _resample(df, resample)
        result[symbols[0]] = df
    else:
        for sym in symbols:
            df = _extract_single(data, sym)
            if df is not None and resample:
                df = _resample(df, resample)
            result[sym] = df
    return result


def fetch_all(
    symbols,
    long_iv, long_p, long_rs,
    mid_iv, mid_p, mid_rs,
    short_iv, short_p, short_rs,
):
    """長期・中期・短期の 3 時間軸を一括取得して返す。各タプル (interval, period, resample)。"""
    long_data = fetch_multi(symbols, long_iv, long_p, long_rs)
    mid_data = fetch_multi(symbols, mid_iv, mid_p, mid_rs)
    short_data = fetch_multi(symbols, short_iv, short_p, short_rs)
    return long_data, mid_data, short_data
