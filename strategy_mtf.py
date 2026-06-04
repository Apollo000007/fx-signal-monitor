"""MTF — Multi-TimeFrame full-alignment 手法。

設計思想 (ユーザー要望):
  週足・日足・4時間足・1時間足が**全て同じトレンド方向**に揃ったときだけ、
  15分足でその方向のチャート/ローソク足パターン(S/Aランク)が出たらエントリー。

  = PA手法(D1+4H一致+15Mパターン)の上位版。整合する時間軸を4軸に強化した
    順張り「全軸一致」高確度セットアップ。低頻度・高精度。

ルール (機械的):
  1. 各TF(W1/D1/4H/1H)を analyze_timeframe で判定 → direction(up/down/range)。
     全4軸が up → long、全4軸が down → short。1つでも range/不一致なら見送り。
  2. 15M(確定足)で patterns.detect → aligned 方向の S/A ランクパターンを採用。
  3. SL = パターン構造(ヒゲ先/ネック等)=1R、TP = 3R。api 側で最低2R床を保証。
  4. is_alert = 4軸一致 + S/Aトリガー + スコア閾値 + SL/TP整合。

週足は日足 df を resample して内部生成する (新規fetch不要・backtest互換)。
戻り値は strategy_pa と同じ dict 形式 (+ pattern/rank/pattern_name)。
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from strategy import analyze_timeframe
import patterns as pat

# ランク別の基礎点 (S/A のみ採用)
_RANK_BASE = {"S": 55, "A": 45}


def _safe(x, fb=0.0) -> float:
    try:
        if x is None or pd.isna(x):
            return fb
        return float(x)
    except (TypeError, ValueError):
        return fb


def _empty(pair: str, symbol: str, reasons=None) -> dict:
    return {
        "pair": pair,
        "symbol": symbol,
        "direction": "none",
        "entry_type": "none",
        "score": 0,
        "price": 0.0,
        "stop_loss": None,
        "take_profit": None,
        "reasons": list(reasons or []),
        "warnings": [],
        "has_trigger": False,
        "is_alert": False,
        "pattern": None,
        "rank": None,
        "pattern_name": None,
    }


def _to_weekly(df_long: pd.DataFrame) -> Optional[pd.DataFrame]:
    """日足 df を週足 OHLC に resample。"""
    if df_long is None or len(df_long) < 20:
        return None
    try:
        w = df_long.resample("1W").agg(
            {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
        ).dropna()
        return w if len(w) >= 60 else (w if len(w) >= 30 else None)
    except Exception:
        return None


def _tf_dir(df: pd.DataFrame, min_bars: int = 60) -> tuple[str, Optional[object]]:
    """analyze_timeframe の direction を long/short/none に写像。"""
    if df is None or len(df) < min_bars:
        return "none", None
    try:
        a = analyze_timeframe(df)
    except Exception:
        return "none", None
    d = getattr(a, "direction", "range")
    if d == "up":
        return "long", a
    if d == "down":
        return "short", a
    return "none", a


def analyze_pair_mtf(
    pair: str,
    symbol: str,
    df_long: pd.DataFrame,
    df_mid: pd.DataFrame,
    df_short: pd.DataFrame,
    df_h1: Optional[pd.DataFrame] = None,
    alert_threshold: int = 75,
) -> dict:
    """MTF 全軸一致手法の判定 (dict を返す)。"""
    if df_short is None or len(df_short) < 30:
        return _empty(pair, symbol, ["データ不足 (MTF 15M)"])
    if df_long is None or df_mid is None or len(df_long) < 120 or len(df_mid) < 60:
        return _empty(pair, symbol, ["データ不足 (MTF HTF)"])

    result = _empty(pair, symbol)
    # 評価は直近の確定 15M 足。進行中バーは使わない。
    df_eval = df_short.iloc[:-1] if len(df_short) >= 2 else df_short
    price = _safe(df_eval["Close"].iloc[-1])
    result["price"] = price

    # ---- 1) 4軸トレンド方向 ----
    df_week = _to_weekly(df_long)
    if df_week is None:
        return _empty(pair, symbol, ["データ不足 (MTF 週足resample)"])

    w_dir, _ = _tf_dir(df_week, min_bars=40)
    d_dir, _ = _tf_dir(df_long, min_bars=120)
    m_dir, _ = _tf_dir(df_mid, min_bars=60)
    h_dir, _ = _tf_dir(df_h1, min_bars=60) if df_h1 is not None else ("none", None)

    dirs = {"週足": w_dir, "日足": d_dir, "4H": m_dir, "1H": h_dir}
    label = {"long": "買い", "short": "売り", "none": "レンジ/不明"}
    result["reasons"].append(
        "各軸: " + " / ".join(f"{k}={label[v]}" for k, v in dirs.items())
    )

    aligned = None
    if all(v == "long" for v in dirs.values()):
        aligned = "long"
    elif all(v == "short" for v in dirs.values()):
        aligned = "short"

    if aligned is None:
        result["entry_type"] = "wait"
        result["reasons"].append("4軸トレンド不一致 — 見送り (全軸一致が条件)")
        return result

    result["direction"] = aligned
    result["entry_type"] = f"mtf_{aligned}"
    result["reasons"].append(
        f"★週/日/4H/1H 全軸が{label[aligned]}トレンド一致 (+50)"
    )
    score = 50

    # ---- 2) 15M S/A パターン (aligned 方向) ----
    matches = pat.detect(df_eval)
    cands = [m for m in matches
             if m.get("sig") == aligned and pat.rank_of(m.get("key", "")) in ("S", "A")]
    if not cands:
        result["reasons"].append("15Mに方向一致のS/Aパターンなし — トリガー待ち")
        # 4軸は揃っているがトリガー未発火 → スコアは閾値未満にキャップ
        result["score"] = min(score, alert_threshold - 5)
        return result

    cands.sort(key=lambda m: (pat.RANK_ORDER.get(pat.rank_of(m["key"]), 0),
                              m.get("strength", 0.0)), reverse=True)
    best = cands[0]
    key = best["key"]
    rank = pat.rank_of(key)
    meta = pat.meta_of(key)
    result["pattern"] = key
    result["rank"] = rank
    result["pattern_name"] = meta.get("name", key)
    result["has_trigger"] = True
    score += _RANK_BASE.get(rank, 45)
    score += int(round(best.get("strength", 0.0) * 10))
    result["reasons"].append(
        f"★15M【{rank}】{meta.get('name', key)} ({meta.get('en','')}) — {meta.get('m','')}"
    )
    if meta.get("fk"):
        result["warnings"].append(f"ダマシ注意: {meta['fk']}")

    # ---- 3) SL / TP (構造SL=1R, 固定3R) ----
    sl_hint = best.get("sl_hint")
    if sl_hint is None or sl_hint <= 0:
        result["entry_type"] = "wait"
        result["reasons"].append("構造的SLを取れないパターン — 見送り")
        result["score"] = min(score, alert_threshold - 5)
        return result
    buf = price * (0.0010 if "JPY" in symbol.upper() else 0.0008)
    sl = (sl_hint - buf) if aligned == "long" else (sl_hint + buf)
    r = abs(price - sl)
    if r <= 0 or (aligned == "long" and sl >= price) or (aligned == "short" and sl <= price):
        result["entry_type"] = "wait"
        result["reasons"].append("SL整合せず — 見送り")
        result["score"] = min(score, alert_threshold - 5)
        return result
    tp = price + 3.0 * r if aligned == "long" else price - 3.0 * r
    result["stop_loss"] = sl
    result["take_profit"] = tp
    result["reasons"].append(f"SL={sl:.5f} (パターン構造=1R) / TP={tp:.5f} (固定3R)")

    result["score"] = min(int(score), 100)
    result["is_alert"] = bool(
        result["has_trigger"]
        and result["score"] >= alert_threshold
        and aligned in ("long", "short")
    )
    return result
