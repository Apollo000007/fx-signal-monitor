"""Claude Confluence 手法 — 正の期待値を狙った合流型トレンドフォロー。

設計思想 (エビデンスベース):
  - Moskowitz/Ooi/Pedersen (2012) "Time Series Momentum": 複数時間軸のモメンタム持続が
    FX を含む資産群で統計的に有意な正リターン。
  - Turtle / Donchian Breakout: 古典的な N 本高値ブレイクで長期正期待値。
  - Linda Raschke "Anti" setup: トレンド再加速直後のプルバックエントリー。
  - Volatility Compression (NR7 / Crabel): ATR 収縮後のブレイクは勝率と値幅の両面で優位。
  - Mean reversion to 20 EMA (Connors 系): 強トレンドでは 20EMA への浅い押しが高勝率の入口。

6 つのエッジを合流させ、4 つ以上が揃った時のみ★トリガー発火として
『勝てる合流点』のみを拾う設計。リスクリワードは常に 1:2 以上 (SL 1.5×ATR, TP 3.0×ATR)
 を確保して期待値ベースで黒字化を狙う。

ルール:
  1. HTF バイアス: 日足・4H 両方が EMA50 より上/下 (両軸一致)
  2. 4H モメンタム: RSI(14) が 50–70 (long) / 30–50 (short) かつ MACD ヒスト同方向
  3. 15M ATR 収縮: 直近 5 本平均 ATR < 100 本平均 ATR × 0.7
  4. 15M プルバック: 価格が 15M 20EMA の ±0.15% 以内
  5. 15M モメンタム再加速: RSI(14) が 50 を反対側から再奪取
  6. ★15M ブレイクトリガー: 直近 20 本の高値/安値を同方向陽線/陰線で抜けて終値確定
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from indicators import atr, ema, macd, rsi


def _safe(x, fb=0.0):
    try:
        if x is None or pd.isna(x):
            return fb
        return float(x)
    except (TypeError, ValueError):
        return fb


# ================== サブ判定 ==================

def _htf_bias(df_long: pd.DataFrame, df_mid: pd.DataFrame) -> tuple[str, list]:
    """日足 + 4H 両方の EMA50 でバイアスを決定。両軸一致時のみ方向性あり。"""
    reasons: list = []
    if df_long is None or df_mid is None:
        return "none", reasons
    if len(df_long) < 60 or len(df_mid) < 60:
        return "none", reasons

    d_close = df_long["Close"]
    m_close = df_mid["Close"]
    d_ema = ema(d_close, 50)
    m_ema = ema(m_close, 50)

    dc = _safe(d_close.iloc[-1])
    de = _safe(d_ema.iloc[-1])
    mc = _safe(m_close.iloc[-1])
    me = _safe(m_ema.iloc[-1])
    if not (dc and de and mc and me):
        return "none", reasons

    d_up = dc > de
    m_up = mc > me
    if d_up and m_up:
        reasons.append("日足・4H 両方とも EMA50 上 (強気バイアス一致)")
        return "up", reasons
    if (not d_up) and (not m_up):
        reasons.append("日足・4H 両方とも EMA50 下 (弱気バイアス一致)")
        return "down", reasons

    reasons.append(
        f"HTF バイアス不一致 (日足:{'↑' if d_up else '↓'} / 4H:{'↑' if m_up else '↓'})"
    )
    return "none", reasons


def _mid_momentum(df_mid: pd.DataFrame, direction: str) -> tuple[int, list]:
    """4H の RSI + MACD でモメンタム確認。最大 15 点。"""
    reasons: list = []
    if df_mid is None or len(df_mid) < 50:
        return 0, reasons

    close = df_mid["Close"]
    r14 = rsi(close, 14)
    _, _, hist = macd(close, 12, 26, 9)

    cur_r = _safe(r14.iloc[-1])
    cur_h = _safe(hist.iloc[-1])

    pts = 0
    if direction == "long":
        if 50 < cur_r < 70:
            pts += 8
            reasons.append(f"4H RSI {cur_r:.0f} (モメンタム圏)")
        elif cur_r >= 70:
            reasons.append(f"4H RSI {cur_r:.0f} (買われ過ぎ: 追随注意)")
        else:
            reasons.append(f"4H RSI {cur_r:.0f} (モメンタム弱)")
        if cur_h > 0:
            pts += 7
            reasons.append(f"4H MACDヒスト +{cur_h:.5f}")
    elif direction == "short":
        if 30 < cur_r < 50:
            pts += 8
            reasons.append(f"4H RSI {cur_r:.0f} (モメンタム圏)")
        elif cur_r <= 30:
            reasons.append(f"4H RSI {cur_r:.0f} (売られ過ぎ: 追随注意)")
        else:
            reasons.append(f"4H RSI {cur_r:.0f} (モメンタム弱)")
        if cur_h < 0:
            pts += 7
            reasons.append(f"4H MACDヒスト {cur_h:.5f}")
    return pts, reasons


def _atr_contraction(df_short: pd.DataFrame) -> tuple[int, list]:
    """15M ATR の収縮度合いを測定。0.7 倍以下で 15 点 (コイル状態)。"""
    reasons: list = []
    if df_short is None or len(df_short) < 120:
        return 0, reasons
    a = atr(df_short["High"], df_short["Low"], df_short["Close"], 14)
    recent = _safe(a.iloc[-5:].mean())
    baseline = _safe(a.iloc[-100:].mean())
    if baseline <= 0 or recent <= 0:
        return 0, reasons
    ratio = recent / baseline
    if ratio < 0.7:
        reasons.append(f"15M ATR 収縮 ({ratio:.2f}×) → ブレイク期待値高")
        return 15, reasons
    if ratio < 0.9:
        reasons.append(f"15M ATR やや収束 ({ratio:.2f}×)")
        return 8, reasons
    reasons.append(f"15M ATR 通常 ({ratio:.2f}×)")
    return 0, reasons


def _ema_pullback(df_short: pd.DataFrame, direction: str) -> tuple[int, list]:
    """15M 価格が 20EMA 付近 (±0.15%) にあるか = 浅い押し目。"""
    reasons: list = []
    if df_short is None or len(df_short) < 30:
        return 0, reasons
    close = df_short["Close"]
    e20 = ema(close, 20)
    price = _safe(close.iloc[-1])
    ev = _safe(e20.iloc[-1])
    if price <= 0 or ev <= 0:
        return 0, reasons
    dist = abs(price - ev) / ev

    if direction == "long":
        if dist < 0.0015 and price >= ev * 0.9995:
            reasons.append("15M 20EMA タッチ (押し目完了)")
            return 15, reasons
        if dist < 0.003:
            reasons.append(f"15M 20EMA 近傍 (距離 {dist*100:.2f}%)")
            return 6, reasons
    elif direction == "short":
        if dist < 0.0015 and price <= ev * 1.0005:
            reasons.append("15M 20EMA タッチ (戻り売り好機)")
            return 15, reasons
        if dist < 0.003:
            reasons.append(f"15M 20EMA 近傍 (距離 {dist*100:.2f}%)")
            return 6, reasons
    return 0, reasons


def _rsi_reclaim(df_short: pd.DataFrame, direction: str) -> tuple[int, list]:
    """15M RSI(14) が 50 を反対側から再奪取 = モメンタム再加速。"""
    reasons: list = []
    if df_short is None or len(df_short) < 30:
        return 0, reasons
    r14 = rsi(df_short["Close"], 14)
    cur = _safe(r14.iloc[-1])
    prev3 = _safe(r14.iloc[-4]) if len(r14) >= 4 else cur

    if direction == "long":
        if prev3 < 50 <= cur:
            reasons.append(f"15M RSI 50 再奪取 ({prev3:.0f}→{cur:.0f})")
            return 10, reasons
        if cur >= 55:
            reasons.append(f"15M RSI {cur:.0f} (強気維持)")
            return 5, reasons
    elif direction == "short":
        if prev3 > 50 >= cur:
            reasons.append(f"15M RSI 50 割れ ({prev3:.0f}→{cur:.0f})")
            return 10, reasons
        if cur <= 45:
            reasons.append(f"15M RSI {cur:.0f} (弱気維持)")
            return 5, reasons
    return 0, reasons


def _donchian_trigger(df_short: pd.DataFrame, direction: str) -> tuple[bool, int, list, Optional[float]]:
    """★ Donchian 20 本ブレイク = エントリートリガー。最大 15 点。"""
    reasons: list = []
    if df_short is None or len(df_short) < 25:
        return False, 0, reasons, None
    lookback = 20
    win = df_short.iloc[-(lookback + 1):-1]
    last = df_short.iloc[-1]
    win_high = float(win["High"].max())
    win_low = float(win["Low"].min())

    last_close = float(last["Close"])
    last_open = float(last["Open"])
    body_ratio = abs(last_close - last_open) / max(float(last["High"]) - float(last["Low"]), 1e-9)

    if direction == "long":
        if last_close > win_high and last_close > last_open and body_ratio > 0.4:
            reasons.append(f"★15M Donchian {lookback}本高値ブレイク ({win_high:.5f})")
            return True, 15, reasons, win_high
    elif direction == "short":
        if last_close < win_low and last_close < last_open and body_ratio > 0.4:
            reasons.append(f"★15M Donchian {lookback}本安値ブレイク ({win_low:.5f})")
            return True, 15, reasons, win_low
    return False, 0, reasons, None


# ================== メイン ==================

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
    }


def analyze_pair_claude(
    pair: str,
    symbol: str,
    df_long: pd.DataFrame,
    df_mid: pd.DataFrame,
    df_short: pd.DataFrame,
    alert_threshold: int = 75,
) -> dict:
    """Claude Confluence 手法の判定を返す (dict)。"""
    if df_short is None or len(df_short) < 120:
        return _empty(pair, symbol, ["データ不足 (Claude Confluence)"])
    if df_long is None or df_mid is None or len(df_long) < 60 or len(df_mid) < 60:
        return _empty(pair, symbol, ["データ不足 (Claude Confluence HTF)"])

    price = _safe(df_short["Close"].iloc[-1])
    result = _empty(pair, symbol)
    result["price"] = price

    # --- 1) HTF バイアス ---
    direction, bias_reasons = _htf_bias(df_long, df_mid)
    result["reasons"].extend(bias_reasons)
    if direction == "none":
        result["entry_type"] = "wait"
        return result
    result["direction"] = "long" if direction == "up" else "short"
    dir_simple = result["direction"]

    score = 20  # HTF alignment base
    result["reasons"].append("→ HTF 整合 (+20)")

    # --- 2) 4H モメンタム ---
    m_pts, m_reasons = _mid_momentum(df_mid, dir_simple)
    score += m_pts
    result["reasons"].extend(m_reasons)

    # --- 3) 15M ATR 収縮 ---
    a_pts, a_reasons = _atr_contraction(df_short)
    score += a_pts
    result["reasons"].extend(a_reasons)

    # --- 4) 15M 20EMA プルバック ---
    e_pts, e_reasons = _ema_pullback(df_short, dir_simple)
    score += e_pts
    result["reasons"].extend(e_reasons)

    # --- 5) 15M RSI 再奪取 ---
    r_pts, r_reasons = _rsi_reclaim(df_short, dir_simple)
    score += r_pts
    result["reasons"].extend(r_reasons)

    # --- 6) ★Donchian ブレイク ---
    triggered, t_pts, t_reasons, break_level = _donchian_trigger(df_short, dir_simple)
    score += t_pts
    result["reasons"].extend(t_reasons)
    result["has_trigger"] = triggered

    # --- エントリータイプ ---
    result["entry_type"] = (
        "claude_confluence_long" if dir_simple == "long" else "claude_confluence_short"
    )

    # --- SL / TP: ATR ベース (リスクリワード 1:2) ---
    a = atr(df_short["High"], df_short["Low"], df_short["Close"], 14)
    av = _safe(a.iloc[-1])
    if av <= 0:
        av = price * 0.002  # フォールバック: 0.2%

    if dir_simple == "long":
        result["stop_loss"] = price - 1.5 * av
        result["take_profit"] = price + 3.0 * av  # 2R
    else:
        result["stop_loss"] = price + 1.5 * av
        result["take_profit"] = price - 3.0 * av

    result["score"] = min(int(score), 100)
    result["is_alert"] = (
        result["has_trigger"]
        and result["score"] >= alert_threshold
        and dir_simple != "none"
    )

    # トリガー未発火ならスコアをキャップ (他手法と整合)
    if not result["has_trigger"]:
        result["score"] = min(result["score"], alert_threshold - 5)

    return result
