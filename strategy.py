"""ORZ手法準拠のシグナル判定。

参照記事: https://xn--fx-ph4angpet59xn23a.jp/?p=1853
『移動平均線&一目均衡表で短期〜長期トレードまでカバーするシンプルFX手法』

使用インジケーター (ORZ流):
  - 移動平均線3本 (SMA 20 / 50 / 100)
  - 一目均衡表の「雲」のみ (先行スパンA/B)
  - ※ MACD は使わない

時間軸構成:
  - 長期 (日足) : 大局環境 — 方向性と障害物の確認
  - 中期 (4H)  : メイン判定 — 相場タイプ分類と根拠となるポイント決定
  - 短期 (15M) : エントリータイミング — 反発・ブレイク挙動の確認

相場判断:
  ORZ 流に「わかりやすい相場だけ厳選」する。以下3つに分類:
    - trend_up / trend_down : SMAの順序・傾斜・雲の位置が揃ったトレンド
    - range                 : SMAが水平で上下ラインが明確に機能している
    - unclear               : どちらでもない (スキップ)

エントリーパターン (ORZ流):
  1. pullback        : トレンド中の押し目買い・戻り売り
                       (実績SMAへの接触 or レジサポとの複合根拠)
  2. breakout        : トレンド中の保ち合い (レジサポ) ブレイクアウト
                       (ダマシ回避のため下位足でフォロースルー確認)
  3. range_reversal  : レンジの上下ラインからの逆張り

最終発火:
  各エントリー候補に対し 15M 足で反発 / ブレイクの挙動を確認できたら
  "★15Mトリガー" を立てて alert 対象スコアに到達させる。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from indicators import sma, ichimoku, find_swings, cluster_levels, slope


# ================= 時間軸分析 =================

@dataclass
class TimeframeAnalysis:
    direction: str          # "up" / "down" / "range"
    regime: str             # "trend_up" / "trend_down" / "range" / "unclear"
    clarity: int            # 0-100 わかりやすさ
    close: float
    sma20: float
    sma50: float
    sma100: float
    slope20: float          # % / 5bars
    slope50: float
    slope100: float
    cloud_top: float
    cloud_bottom: float
    price_vs_cloud: str     # "above" / "below" / "inside"
    macd_hist: float = 0.0  # (旧互換。ORZ手法では未使用)
    last_swing_high: Optional[float] = None
    last_swing_low: Optional[float] = None
    resistances: list = field(default_factory=list)
    supports: list = field(default_factory=list)
    range_top: Optional[float] = None
    range_bottom: Optional[float] = None


def _safe(val, fallback=0.0) -> float:
    try:
        if val is None or pd.isna(val):
            return fallback
        return float(val)
    except (TypeError, ValueError):
        return fallback


def _classify_regime(
    c: float,
    s20v: float, s50v: float, s100v: float,
    sl20: float, sl50: float, sl100: float,
    pvc: str,
    swing_highs: list, swing_lows: list,
    all_res: list, all_sup: list,
):
    """ORZ 流の相場タイプ判定。"""
    up_order = s20v > s50v > s100v
    dn_order = s20v < s50v < s100v
    up_slope = sl20 > 0.05 and sl50 >= 0.0
    dn_slope = sl20 < -0.05 and sl50 <= 0.0

    if up_order and up_slope:
        clarity = 50
        if pvc == "above":
            clarity += 30
        elif pvc == "inside":
            clarity += 10
        if len(swing_highs) >= 2 and swing_highs[-1][1] > swing_highs[-2][1]:
            clarity += 10
        if len(swing_lows) >= 2 and swing_lows[-1][1] > swing_lows[-2][1]:
            clarity += 10
        return min(clarity, 100), "trend_up", "up"

    if dn_order and dn_slope:
        clarity = 50
        if pvc == "below":
            clarity += 30
        elif pvc == "inside":
            clarity += 10
        if len(swing_highs) >= 2 and swing_highs[-1][1] < swing_highs[-2][1]:
            clarity += 10
        if len(swing_lows) >= 2 and swing_lows[-1][1] < swing_lows[-2][1]:
            clarity += 10
        return min(clarity, 100), "trend_down", "down"

    # レンジ判定: SMAの傾斜が小さく、明確な上下ラインがある
    flat = abs(sl20) < 0.08 and abs(sl50) < 0.05
    if flat and all_res and all_sup:
        clarity = 50
        if len(all_res) >= 1 and len(all_sup) >= 1:
            clarity += 15
        top = all_res[-1]
        bot = all_sup[0]
        if bot < c < top:
            clarity += 15
        return min(clarity, 100), "range", "range"

    return 0, "unclear", "range"


def analyze_timeframe(df: pd.DataFrame) -> TimeframeAnalysis:
    close = df["Close"]
    high = df["High"]
    low = df["Low"]

    s20 = sma(close, 20)
    s50 = sma(close, 50)
    s100 = sma(close, 100)
    _, _, senkou_a, senkou_b = ichimoku(high, low)

    c = _safe(close.iloc[-1])
    s20v = _safe(s20.iloc[-1], c)
    s50v = _safe(s50.iloc[-1], c)
    s100v = _safe(s100.iloc[-1], c)
    sa = _safe(senkou_a.iloc[-1], c)
    sb = _safe(senkou_b.iloc[-1], c)
    cloud_top = max(sa, sb)
    cloud_bottom = min(sa, sb)

    if c > cloud_top:
        pvc = "above"
    elif c < cloud_bottom:
        pvc = "below"
    else:
        pvc = "inside"

    sl20 = slope(s20, 5)
    sl50 = slope(s50, 5)
    sl100 = slope(s100, 5)

    swing_highs, swing_lows = find_swings(df, window=3)
    last_sh = swing_highs[-1][1] if swing_highs else None
    last_sl = swing_lows[-1][1] if swing_lows else None

    # レジサポ候補: 直近20スイングをクラスタリング
    high_levels = [p for _, p in swing_highs[-20:]]
    low_levels = [p for _, p in swing_lows[-20:]]
    all_res = cluster_levels(high_levels)
    all_sup = cluster_levels(low_levels)
    resistances = sorted([lv for lv in all_res if lv > c])[:3]
    supports = sorted([lv for lv in all_sup if lv < c], reverse=True)[:3]

    clarity, regime, direction = _classify_regime(
        c, s20v, s50v, s100v, sl20, sl50, sl100, pvc,
        swing_highs, swing_lows, all_res, all_sup,
    )

    range_top = all_res[-1] if (regime == "range" and all_res) else None
    range_bottom = all_sup[0] if (regime == "range" and all_sup) else None

    return TimeframeAnalysis(
        direction=direction,
        regime=regime,
        clarity=clarity,
        close=c,
        sma20=s20v, sma50=s50v, sma100=s100v,
        slope20=sl20, slope50=sl50, slope100=sl100,
        cloud_top=cloud_top, cloud_bottom=cloud_bottom,
        price_vs_cloud=pvc,
        last_swing_high=last_sh, last_swing_low=last_sl,
        resistances=resistances, supports=supports,
        range_top=range_top, range_bottom=range_bottom,
    )


# ================= Signal =================

@dataclass
class Signal:
    pair: str
    symbol: str
    direction: str                   # "long" / "short" / "none"
    entry_type: str = "none"         # "pullback" / "breakout" / "range_reversal" / "wait" / "none"
    score: int = 0
    price: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reasons: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    lt: Optional[TimeframeAnalysis] = None
    mt: Optional[TimeframeAnalysis] = None
    st: Optional[TimeframeAnalysis] = None


# ================= エントリー検出 =================

def _detect_pullback(direction: str, mt: TimeframeAnalysis) -> Optional[dict]:
    """押し目買い / 戻り売り候補の検出。

    ORZ 流: SMA (20/50/100) への接触、かつレジサポと重なっていれば複数根拠。
    """
    c = mt.close
    tol_close = 0.003   # 0.3% 以内でタッチ扱い
    bases: list = []

    if direction == "long":
        for name, lv in [("SMA20", mt.sma20), ("SMA50", mt.sma50), ("SMA100", mt.sma100)]:
            if lv and lv > 0 and abs(c - lv) / c < tol_close:
                bases.append(name)
        # SMA20-SMA50 帯への押し
        if not bases and mt.sma50 and mt.sma20 and mt.sma50 < mt.sma20 and mt.sma50 <= c <= mt.sma20:
            bases.append("SMA20-50帯")
        for lv in mt.supports:
            if abs(c - lv) / c < tol_close:
                bases.append(f"サポートライン({lv:.4f})")
                break

    elif direction == "short":
        for name, lv in [("SMA20", mt.sma20), ("SMA50", mt.sma50), ("SMA100", mt.sma100)]:
            if lv and lv > 0 and abs(c - lv) / c < tol_close:
                bases.append(name)
        if not bases and mt.sma50 and mt.sma20 and mt.sma20 < mt.sma50 and mt.sma20 <= c <= mt.sma50:
            bases.append("SMA20-50帯")
        for lv in mt.resistances:
            if abs(c - lv) / c < tol_close:
                bases.append(f"レジスタンスライン({lv:.4f})")
                break

    if not bases:
        return None
    return {"bases": bases, "count": len(bases)}


def _detect_breakout(direction: str, df_mid: pd.DataFrame) -> Optional[dict]:
    """トレンド中の保ち合いブレイク検出。

    直近 N 本の高値安値で作られた狭いレンジを最新足がブレイクしたか。
    """
    if df_mid is None or len(df_mid) < 15:
        return None
    lookback = 12
    window = df_mid.iloc[-(lookback + 2):-2]
    if window.empty:
        return None
    win_high = float(window["High"].max())
    win_low = float(window["Low"].min())
    last_close = float(df_mid["Close"].iloc[-1])
    prev_close = float(df_mid["Close"].iloc[-2])

    width = (win_high - win_low) / max(win_low, 1e-9)
    # ほどほどに狭い保ち合い (0.3% 〜 2.5%)
    if not (0.003 < width < 0.025):
        return None

    if direction == "long" and prev_close <= win_high and last_close > win_high:
        return {"level": win_high, "kind": "upper_break"}
    if direction == "short" and prev_close >= win_low and last_close < win_low:
        return {"level": win_low, "kind": "lower_break"}
    return None


def _detect_range_reversal(mt: TimeframeAnalysis) -> Optional[dict]:
    """レンジ上下ライン付近からの逆張り候補。"""
    if mt.regime != "range":
        return None
    if mt.range_top is None or mt.range_bottom is None:
        return None
    c = mt.close
    rng = mt.range_top - mt.range_bottom
    if rng <= 0:
        return None
    upper_band = mt.range_top - rng * 0.2
    lower_band = mt.range_bottom + rng * 0.2
    if c >= upper_band:
        return {"direction": "short", "edge": "上端", "level": mt.range_top}
    if c <= lower_band:
        return {"direction": "long", "edge": "下端", "level": mt.range_bottom}
    return None


def _obstacles_in_path(direction: str, price: float, lt: TimeframeAnalysis, threshold: float = 0.006):
    """日足の障害物 (SMA50/100, 雲) を検出。"""
    obstacles = []
    if direction == "long":
        for level, name in [
            (lt.sma50, "日足SMA50"),
            (lt.sma100, "日足SMA100"),
            (lt.cloud_top, "日足雲上端"),
        ]:
            if level and level > price and (level - price) / price < threshold:
                obstacles.append(f"{name}({level:.4f})")
    elif direction == "short":
        for level, name in [
            (lt.sma50, "日足SMA50"),
            (lt.sma100, "日足SMA100"),
            (lt.cloud_bottom, "日足雲下端"),
        ]:
            if level and level < price and (price - level) / price < threshold:
                obstacles.append(f"{name}({level:.4f})")
    return obstacles


def _reversal_trigger(df_short: pd.DataFrame, direction: str) -> list:
    """15M 足で反発挙動を確認 (ORZ流の『下位足で反発の挙動を確認』)。"""
    if df_short is None or len(df_short) < 10:
        return []
    last = df_short.iloc[-1]
    prev = df_short.iloc[-2]
    highs = df_short["High"].tail(10).values
    lows = df_short["Low"].tail(10).values
    opens = df_short["Open"].tail(10).values

    triggers = []
    body = abs(last["Close"] - last["Open"]) or 1e-9

    if direction == "long":
        prev_min = lows[:-1].min()
        if lows[-1] > prev_min and last["Close"] > last["Open"] and last["Close"] > prev["Close"]:
            triggers.append("安値切り上げ+陽線")
        lower_wick = min(last["Open"], last["Close"]) - last["Low"]
        if lower_wick > body * 1.5 and last["Close"] >= last["Open"]:
            triggers.append("下ヒゲピンバー")
        if len(lows) >= 5:
            low_min = lows[-5:-1].min()
            if abs(lows[-2] - low_min) / max(low_min, 1e-9) < 0.0015 and last["Close"] > opens[-1]:
                triggers.append("ダブルボトム形成")

    elif direction == "short":
        prev_max = highs[:-1].max()
        if highs[-1] < prev_max and last["Close"] < last["Open"] and last["Close"] < prev["Close"]:
            triggers.append("高値切り下げ+陰線")
        upper_wick = last["High"] - max(last["Open"], last["Close"])
        if upper_wick > body * 1.5 and last["Close"] <= last["Open"]:
            triggers.append("上ヒゲピンバー")
        if len(highs) >= 5:
            high_max = highs[-5:-1].max()
            if abs(highs[-2] - high_max) / max(high_max, 1e-9) < 0.0015 and last["Close"] < opens[-1]:
                triggers.append("ダブルトップ形成")

    return triggers


def _breakout_trigger(df_short: pd.DataFrame, direction: str) -> list:
    """15M でブレイク方向へのフォロースルーを確認 (ダマシ回避)。"""
    if df_short is None or len(df_short) < 5:
        return []
    last = df_short.iloc[-1]
    prev = df_short.iloc[-2]
    triggers: list = []
    rng = last["High"] - last["Low"]
    if rng <= 0:
        return triggers
    body = abs(last["Close"] - last["Open"])
    body_ratio = body / rng

    if direction == "long":
        if last["Close"] > last["Open"] and last["Close"] > prev["High"] and body_ratio > 0.5:
            triggers.append("ブレイク方向陽線フォロースルー")
    elif direction == "short":
        if last["Close"] < last["Open"] and last["Close"] < prev["Low"] and body_ratio > 0.5:
            triggers.append("ブレイク方向陰線フォロースルー")
    return triggers


# ================= メイン分析 =================

def analyze_pair(pair: str, symbol: str, df_long, df_mid, df_short) -> Signal:
    if df_long is None or df_mid is None or df_short is None:
        return Signal(pair=pair, symbol=symbol, direction="none",
                      reasons=["データ取得失敗"])
    if len(df_long) < 100 or len(df_mid) < 100 or len(df_short) < 30:
        return Signal(pair=pair, symbol=symbol, direction="none",
                      reasons=[f"データ不足 (日足={len(df_long)} 4H={len(df_mid)} 15M={len(df_short)})"])

    lt = analyze_timeframe(df_long)
    mt = analyze_timeframe(df_mid)
    st = analyze_timeframe(df_short)

    sig = Signal(
        pair=pair, symbol=symbol, direction="none",
        entry_type="none", price=mt.close,
        lt=lt, mt=mt, st=st,
    )

    # --- ORZ流: わかりにくい相場はスキップ ---
    if mt.regime == "unclear":
        sig.reasons.append("4H 相場不明瞭: 見送り (ORZ流・わかりやすい相場のみ狙う)")
        return sig
    if mt.clarity < 40:
        sig.reasons.append(f"4H 明瞭度 {mt.clarity}/100: 見送り")
        return sig

    score = 0

    # 1) 4H明瞭度 (0-30点)
    clarity_pts = int(round(mt.clarity * 0.3))
    score += clarity_pts
    label_map = {
        "trend_up": "上昇トレンド",
        "trend_down": "下降トレンド",
        "range": "レンジ",
    }
    sig.reasons.append(
        f"4H {label_map.get(mt.regime, mt.regime)} / 明瞭度 {mt.clarity}/100 "
        f"(SMA傾斜 20:{mt.slope20:+.2f}% 50:{mt.slope50:+.2f}%)"
    )

    # ============= トレンド戦略 =============
    if mt.regime in ("trend_up", "trend_down"):
        direction = "long" if mt.regime == "trend_up" else "short"
        sig.direction = direction

        # 2) 日足環境 (0-15点)
        lt_aligned = (
            (direction == "long" and lt.regime == "trend_up") or
            (direction == "short" and lt.regime == "trend_down")
        )
        lt_counter = (
            (direction == "long" and lt.regime == "trend_down") or
            (direction == "short" and lt.regime == "trend_up")
        )
        if lt_aligned:
            score += 15
            sig.reasons.append("日足も同方向トレンド (環境◎)")
        elif lt.regime == "range":
            score += 7
            sig.reasons.append("日足レンジ (環境△)")
        elif lt_counter:
            sig.warnings.append("日足は逆トレンド - 環境に逆行")
        else:
            score += 3
            sig.reasons.append("日足は不明瞭")

        # 3) エントリーポイント判定 (0-25点)
        pullback = _detect_pullback(direction, mt)
        breakout = _detect_breakout(direction, df_mid) if not pullback else None

        if pullback:
            sig.entry_type = "pullback"
            bases = pullback["bases"]
            # 単独根拠=20, 複数根拠=25
            score += 25 if pullback["count"] >= 2 else 20
            sig.reasons.append(f"4H 押し目/戻り目 ({'+'.join(bases)})")
        elif breakout:
            sig.entry_type = "breakout"
            score += 22
            sig.reasons.append(f"4H 保ち合いブレイク ({breakout['level']:.4f})")
        else:
            sig.entry_type = "wait"
            sig.reasons.append("エントリーポイント未到達 (引きつけ待ち)")

        # 4) 日足障害物チェック (0-10点)
        obstacles = _obstacles_in_path(direction, mt.close, lt)
        if obstacles:
            sig.warnings.append("進行方向の障害物: " + ", ".join(obstacles))
        else:
            score += 10
            sig.reasons.append("日足に障害物なし")

        # 5) 15Mトリガー (0-20点)  ★実際のエントリーサイン★
        if sig.entry_type == "pullback":
            trigger = _reversal_trigger(df_short, direction)
        elif sig.entry_type == "breakout":
            trigger = _breakout_trigger(df_short, direction)
        else:
            trigger = []
        if trigger:
            score += 20
            sig.reasons.append("★15Mトリガー: " + ", ".join(trigger))
        else:
            sig.reasons.append("15Mトリガー未発生 (セットアップ待機)")

        # --- SL / TP ---
        if direction == "long":
            anchor_cands = [v for v in [mt.sma50, mt.last_swing_low] if v]
            anchor = min(anchor_cands) if anchor_cands else mt.sma50
            sig.stop_loss = anchor * 0.998 if anchor else None
            sig.take_profit = lt.resistances[0] if lt.resistances else None
        else:
            anchor_cands = [v for v in [mt.sma50, mt.last_swing_high] if v]
            anchor = max(anchor_cands) if anchor_cands else mt.sma50
            sig.stop_loss = anchor * 1.002 if anchor else None
            sig.take_profit = lt.supports[0] if lt.supports else None

    # ============= レンジ戦略 (ORZ: レンジは逆張り一択) =============
    elif mt.regime == "range":
        rev = _detect_range_reversal(mt)
        if not rev:
            sig.entry_type = "wait"
            sig.reasons.append("レンジ中央域: エッジへの引きつけ待ち")
            return sig

        direction = rev["direction"]
        sig.direction = direction
        sig.entry_type = "range_reversal"

        # 2) エッジ逆張り (0-25点)
        score += 25
        sig.reasons.append(f"4H レンジ{rev['edge']}からの逆張り候補 ({rev['level']:.4f})")

        # 3) 日足が逆行していないか (0-10点)
        lt_counter = (
            (direction == "long" and lt.regime == "trend_down") or
            (direction == "short" and lt.regime == "trend_up")
        )
        if lt_counter:
            sig.warnings.append("日足は逆方向トレンド - レンジブレイク警戒")
        else:
            score += 10
            sig.reasons.append("日足と整合")

        # 4) 15Mトリガー (0-20点)
        trigger = _reversal_trigger(df_short, direction)
        if trigger:
            score += 20
            sig.reasons.append("★15Mトリガー: " + ", ".join(trigger))
        else:
            sig.reasons.append("15Mトリガー未発生")

        # --- SL / TP (レンジは反対エッジ狙い) ---
        if direction == "long":
            sig.stop_loss = mt.range_bottom * 0.998 if mt.range_bottom else None
            sig.take_profit = mt.range_top
        else:
            sig.stop_loss = mt.range_top * 1.002 if mt.range_top else None
            sig.take_profit = mt.range_bottom

    sig.score = min(score, 100)

    # 15M トリガー未発生ならアラート閾値未満にキャップ
    has_trigger = any(r.startswith("★") for r in sig.reasons)
    if not has_trigger:
        sig.score = min(sig.score, 70)

    return sig
