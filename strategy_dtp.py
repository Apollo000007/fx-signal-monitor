"""DTP — Daily Trend Pullback 手法。

設計思想 (エビデンスベース):
  - 時系列モメンタム (Moskowitz/Ooi/Pedersen 2012): 高 TF トレンドは継続する
  - 押し目買い: トレンド方向の浅い押しは「最も価格効率の良い入口」(Connors 系)
  - タイト SL + 固定 3R: 勝率 40% でも構造的にプラス期待値
  - 多重時間軸一致: ダマシ排除 (TRIPLE が +EV だった本質)

ルール (機械的・裁量ゼロ):
  1. 環境  : 日足 50EMA が上向き かつ 4H 50EMA も上向き (両方一致のみ)
  2. 待機  : 価格が 4H 20EMA まで押す (上昇トレンドの押し目)
  3. 引き金: 15M で陽の包み足 or 下ヒゲピンバーが 20EMA 付近で出る
  4. Entry : その 15M 足の確定後、成行 (= 直近 15M 終値)
  5. SL    : 直近 15M スイング安値の少し下 (タイト、≒ 1R)
  6. TP    : 固定 3R (4H 20EMA 割れでの手仕舞いは EA / 手動側で対応)
  7. リスク: 1 トレード 0.5% (発注側で管理。本モジュールは SL/TP のみ提示)
  8. 時間  : ロンドン (7-16 UTC) または NY (12-21 UTC) のみ

下降トレンドは完全に鏡写し (50EMA 下向き + 戻り売り)。

戻り値は strategy_claude と同じ dict 形式。
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from indicators import ema, slope, find_swings


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
    }


# ============== サブ判定 ==============

def _htf_bias(df_long: pd.DataFrame, df_mid: pd.DataFrame) -> tuple[str, list]:
    """日足 50EMA と 4H 50EMA の傾斜が両方一致したときのみ方向を返す。"""
    reasons: list = []
    if df_long is None or df_mid is None:
        return "none", reasons
    if len(df_long) < 60 or len(df_mid) < 60:
        return "none", reasons

    d_ema = ema(df_long["Close"], 50)
    m_ema = ema(df_mid["Close"], 50)

    d_slope = slope(d_ema, 5)   # 直近 5 本の % 変化
    m_slope = slope(m_ema, 5)

    d_c = _safe(df_long["Close"].iloc[-1])
    m_c = _safe(df_mid["Close"].iloc[-1])
    d_e = _safe(d_ema.iloc[-1], d_c)
    m_e = _safe(m_ema.iloc[-1], m_c)

    # 上昇: 両 EMA が上向き かつ 価格が EMA 上
    up = (d_slope > 0.02 and m_slope > 0.02 and d_c > d_e and m_c > m_e)
    dn = (d_slope < -0.02 and m_slope < -0.02 and d_c < d_e and m_c < m_e)

    if up:
        reasons.append(f"日足/4H 両 50EMA 上向き (D:{d_slope:+.2f}% 4H:{m_slope:+.2f}%) — 上昇トレンド一致")
        return "long", reasons
    if dn:
        reasons.append(f"日足/4H 両 50EMA 下向き (D:{d_slope:+.2f}% 4H:{m_slope:+.2f}%) — 下降トレンド一致")
        return "short", reasons

    reasons.append("日足/4H のトレンド不一致 — 見送り")
    return "none", reasons


def _pullback_to_ema20(df_mid: pd.DataFrame, direction: str) -> tuple[int, list, Optional[float]]:
    """価格が 4H 20EMA まで押している (戻している) か。

    上昇 : 終値が 20EMA の ±0.35% 以内 (かつ EMA より上 or 僅差) で押し目成立
    Returns: (加点 0-25, reasons, ema20_value)
    """
    reasons: list = []
    if df_mid is None or len(df_mid) < 30:
        return 0, reasons, None
    e20 = ema(df_mid["Close"], 20)
    ev = _safe(e20.iloc[-1])
    c = _safe(df_mid["Close"].iloc[-1])
    if ev <= 0 or c <= 0:
        return 0, reasons, None
    dist = abs(c - ev) / ev

    if direction == "long":
        if dist < 0.0035:
            reasons.append(f"4H 価格が 20EMA まで押し ({dist*100:.2f}% 以内) — 押し目成立")
            return 25, reasons, ev
        if dist < 0.007:
            reasons.append(f"4H 20EMA 近傍 ({dist*100:.2f}%) — 押し目接近")
            return 12, reasons, ev
    else:  # short
        if dist < 0.0035:
            reasons.append(f"4H 価格が 20EMA まで戻し ({dist*100:.2f}% 以内) — 戻り売り成立")
            return 25, reasons, ev
        if dist < 0.007:
            reasons.append(f"4H 20EMA 近傍 ({dist*100:.2f}%) — 戻り接近")
            return 12, reasons, ev
    return 0, reasons, ev


def _trigger_15m(df_short: pd.DataFrame, direction: str) -> tuple[bool, list]:
    """15M で エントリートリガー (陽/陰の包み足 or ヒゲピンバー)。

    上昇:
      - 陽の包み足: 前足陰線を実体で完全に包む陽線
      - 下ヒゲピンバー: 下ヒゲ > 実体 1.5 倍 かつ 終値 >= 始値
    下降は鏡写し。
    """
    reasons: list = []
    if df_short is None or len(df_short) < 5:
        return False, reasons
    last = df_short.iloc[-1]
    prev = df_short.iloc[-2]

    o, h, l, c = float(last["Open"]), float(last["High"]), float(last["Low"]), float(last["Close"])
    po, pc = float(prev["Open"]), float(prev["Close"])
    body = abs(c - o) or 1e-9
    rng = (h - l) or 1e-9

    if direction == "long":
        engulf = (pc < po) and (c > o) and (c >= po) and (o <= pc)
        lower_wick = min(o, c) - l
        pin = (lower_wick > body * 1.5) and (c >= o)
        if engulf:
            reasons.append("★15M 陽の包み足 (押し目反発)")
            return True, reasons
        if pin:
            reasons.append("★15M 下ヒゲピンバー (押し目反発)")
            return True, reasons
    else:  # short
        engulf = (pc > po) and (c < o) and (c <= po) and (o >= pc)
        upper_wick = h - max(o, c)
        pin = (upper_wick > body * 1.5) and (c <= o)
        if engulf:
            reasons.append("★15M 陰の包み足 (戻り反落)")
            return True, reasons
        if pin:
            reasons.append("★15M 上ヒゲピンバー (戻り反落)")
            return True, reasons
    return False, reasons


def _in_session(df_short: pd.DataFrame) -> tuple[bool, list]:
    """最新 15M 足の時刻が ロンドン (7-16 UTC) or NY (12-21 UTC) か。"""
    reasons: list = []
    if df_short is None or len(df_short) == 0:
        return False, reasons
    ts = df_short.index[-1]
    try:
        hour = ts.tz_convert("UTC").hour if ts.tzinfo else ts.hour
    except Exception:
        hour = getattr(ts, "hour", 12)
    # ロンドン 7-16 / NY 12-21 → 合わせて 7-21 UTC
    if 7 <= hour < 21:
        sess = "ロンドン" if hour < 12 else ("ロンドン+NY" if hour < 16 else "NY")
        reasons.append(f"取引時間内 ({hour:02d}:00 UTC · {sess}セッション)")
        return True, reasons
    reasons.append(f"取引時間外 ({hour:02d}:00 UTC) — 流動性低、見送り")
    return False, reasons


def _swing_sl(df_short: pd.DataFrame, direction: str, entry: float) -> Optional[float]:
    """直近 15M スイング安値/高値の少し外側を SL に。

    上昇: 直近スイング安値 × 0.9990 (= わずか下)
    下降: 直近スイング高値 × 1.0010
    スイングが取れない場合は ATR 代替で entry の ±0.25%
    """
    swing_highs, swing_lows = find_swings(df_short.tail(60), window=3)
    if direction == "long":
        if swing_lows:
            sl = swing_lows[-1][1] * 0.9990
            if sl < entry:
                return sl
        return entry * 0.9975  # fallback ~0.25%
    else:
        if swing_highs:
            sl = swing_highs[-1][1] * 1.0010
            if sl > entry:
                return sl
        return entry * 1.0025


# ============== メイン ==============

def analyze_pair_dtp(
    pair: str,
    symbol: str,
    df_long: pd.DataFrame,
    df_mid: pd.DataFrame,
    df_short: pd.DataFrame,
    alert_threshold: int = 75,
) -> dict:
    """Daily Trend Pullback 手法の判定 (dict を返す)。"""
    if df_short is None or len(df_short) < 30:
        return _empty(pair, symbol, ["データ不足 (DTP 15M)"])
    if df_long is None or df_mid is None or len(df_long) < 60 or len(df_mid) < 60:
        return _empty(pair, symbol, ["データ不足 (DTP HTF)"])

    price = _safe(df_short["Close"].iloc[-1])
    result = _empty(pair, symbol)
    result["price"] = price

    score = 0

    # --- 1) HTF バイアス (日足 + 4H 50EMA 両一致) : 基礎点 35 ---
    direction, bias_reasons = _htf_bias(df_long, df_mid)
    result["reasons"].extend(bias_reasons)
    if direction == "none":
        result["entry_type"] = "wait"
        return result
    result["direction"] = direction
    result["entry_type"] = "dtp_long" if direction == "long" else "dtp_short"
    score += 35
    result["reasons"].append("→ HTF トレンド一致 (+35)")

    # --- 2) 4H 20EMA への押し目/戻り : 0-25 ---
    pb_pts, pb_reasons, _ema20 = _pullback_to_ema20(df_mid, direction)
    score += pb_pts
    result["reasons"].extend(pb_reasons)

    # --- 3) 15M トリガー (包み足 / ピンバー) : 25 ★ ---
    triggered, trig_reasons = _trigger_15m(df_short, direction)
    result["reasons"].extend(trig_reasons)
    if triggered:
        score += 25
    result["has_trigger"] = triggered

    # --- 4) セッションフィルター : 10 ---
    in_sess, sess_reasons = _in_session(df_short)
    result["reasons"].extend(sess_reasons)
    if in_sess:
        score += 10
    else:
        result["warnings"].append("取引時間外シグナル — 流動性に注意")

    # --- 5) 価格と 50EMA の十分な乖離なし (浅い押し) +5 ---
    #     深すぎる押し (トレンド転換の可能性) は減点せず据え置き
    score += 5

    # --- SL / TP ---
    sl = _swing_sl(df_short, direction, price)
    if sl is None:
        result["reasons"].append("SL 算出不可 — 見送り")
        result["entry_type"] = "wait"
        return result
    r = abs(price - sl)
    if r <= 0:
        result["entry_type"] = "wait"
        return result
    tp = price + 3.0 * r if direction == "long" else price - 3.0 * r

    result["stop_loss"] = sl
    result["take_profit"] = tp
    result["reasons"].append(f"SL={sl:.5f} (直近 15M スイング) / TP={tp:.5f} (固定 3R)")

    result["score"] = min(int(score), 100)
    # アラート条件: トリガー発火 + 閾値超過 + セッション内 + 方向確定
    result["is_alert"] = (
        triggered
        and in_sess
        and result["score"] >= alert_threshold
        and direction != "none"
    )

    # トリガー未発火ならスコアを閾値未満にキャップ (他手法と整合)
    if not triggered:
        result["score"] = min(result["score"], alert_threshold - 5)

    return result
