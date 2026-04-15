"""PDH/PDL ブレイクアウト・リテスト手法 (ダマシ回避型)。

参考手法 (要約):
  最大の特徴 = 『ブレイクアウトした瞬間に飛び乗らない (ダマシを回避する)』

  キーレベル:
    - 前日高値 (PDH)  ロング狙いのキーレベル
    - 前日安値 (PDL)  ショート狙いのキーレベル

  ロング手順:
    1. 価格が PDH を明確に上抜け
    2. PDH 付近までリテスト (戻り) を待つ
    3. 短期足 (15M) で『ブルフラッグ』形成確認
    4. 下ヒゲピンバー / 陽の包み足などプライスアクション確認
    5. ブルフラッグ上限ブレイク → エントリー

  ショート手順: 鏡写し (PDL / ベアフラッグ / 上ヒゲ / 陰の包み足)

  フィルター (勝率UP):
    - SMT ダイバージェンス (相関ペアとの整合) — FX なので簡易実装
    - ノートレードゾーン (PDH <-> 当日オープン時間帯の安値 などに挟まれた領域)

時間軸:
  - df_long (日足)  : PDH / PDL を抽出
  - df_mid  (4H)    : 環境確認 (warning 用)
  - df_short(15M)   : ブレイク・リテスト・フラッグ・プライスアクション・トリガー検出

本モジュールは Signal dict (strategy.py と同じ形) を返す純粋関数の集合。
"""
from __future__ import annotations

from typing import Optional

import pandas as pd


# ================== ユーティリティ ==================

def _safe_float(x, fallback=None):
    try:
        if x is None or pd.isna(x):
            return fallback
        return float(x)
    except (TypeError, ValueError):
        return fallback


def _get_pdh_pdl(df_long: pd.DataFrame) -> tuple[Optional[float], Optional[float]]:
    """日足から『前日』の高値・安値を取り出す。

    df_long の末尾が現在日 (未確定) の場合は iloc[-2] を、
    末尾が既に確定足なら iloc[-1] or iloc[-2] のどちらも候補。
    ここでは『最も直近の確定済み日足』= iloc[-2] を前日扱いとする。
    """
    if df_long is None or len(df_long) < 3:
        return None, None
    prev_bar = df_long.iloc[-2]
    return _safe_float(prev_bar["High"]), _safe_float(prev_bar["Low"])


def _pct_dist(a: float, b: float) -> float:
    if not b:
        return 9e9
    return abs(a - b) / abs(b)


# ================== セットアップ検出 ==================

def _detect_long_setup(pdh: float, df_short: pd.DataFrame, lookback: int = 80) -> Optional[dict]:
    """PDH ブレイク → リテスト → ブルフラッグ → プライスアクション → トリガー の検出。

    Returns dict or None. dict は以下のフラグを含む:
      broke, retest, flag, pa_pin, pa_engulf, trigger, flag_upper, score_parts, notes
    """
    if df_short is None or len(df_short) < lookback:
        return None
    win = df_short.tail(lookback).reset_index(drop=True)
    highs = win["High"].values
    lows = win["Low"].values
    closes = win["Close"].values
    opens = win["Open"].values
    n = len(win)

    # ---- 1) PDH ブレイク確認 (先頭〜中盤) ----
    broke_idx = None
    for i in range(n - 4):
        if highs[i] > pdh * 1.0003:  # 0.03% 以上の明確ブレイク
            broke_idx = i
            break
    if broke_idx is None:
        return None

    # ---- 2) リテスト確認 (ブレイク後に PDH 付近まで戻る) ----
    post = win.iloc[broke_idx + 1:]
    if post.empty:
        return None
    # 低値が PDH の ±0.15% 以内まで戻ったか
    retest_hit = False
    retest_idx = None
    for j, lv in enumerate(post["Low"].values):
        if abs(lv - pdh) / pdh < 0.0015:
            retest_hit = True
            retest_idx = broke_idx + 1 + j
            break
    if not retest_hit:
        return None

    # ---- 3) ブルフラッグ (リテスト以降〜最新足直前の最大5本) ----
    flag_slice = win.iloc[max(retest_idx, n - 7): n - 1]
    if len(flag_slice) < 2:
        return None
    fh = flag_slice["High"].values
    fl = flag_slice["Low"].values
    # 高値が概ね切り下がり (±0.05% 許容)
    desc_high = sum(1 for i in range(1, len(fh)) if fh[i] <= fh[i - 1] * 1.0005)
    desc_low = sum(1 for i in range(1, len(fl)) if fl[i] <= fl[i - 1] * 1.0005)
    flag_ok = desc_high >= max(1, len(fh) - 2) and desc_low >= max(1, len(fl) - 2)
    flag_upper = float(fh.max())

    # ---- 4) プライスアクション ----
    last = win.iloc[-1]
    prev = win.iloc[-2]
    body = abs(last["Close"] - last["Open"]) or 1e-9
    rng = last["High"] - last["Low"] or 1e-9
    lower_wick = min(last["Open"], last["Close"]) - last["Low"]
    pin_bar = (lower_wick / rng) > 0.5 and last["Close"] >= last["Open"]
    engulf = (
        prev["Close"] < prev["Open"]
        and last["Close"] > last["Open"]
        and last["Close"] >= prev["Open"]
        and last["Open"] <= prev["Close"]
    )

    # ---- 5) トリガー (最新足がフラッグ上限を上抜けて陽線終値) ----
    trigger = last["Close"] > flag_upper and last["Close"] > last["Open"]

    return {
        "broke": True,
        "broke_idx": int(broke_idx),
        "retest": True,
        "retest_idx": int(retest_idx),
        "flag": flag_ok,
        "pa_pin": bool(pin_bar),
        "pa_engulf": bool(engulf),
        "trigger": bool(trigger),
        "flag_upper": flag_upper,
        "flag_lower": float(fl.min()),
    }


def _detect_short_setup(pdl: float, df_short: pd.DataFrame, lookback: int = 80) -> Optional[dict]:
    """PDL ブレイク → リテスト → ベアフラッグ → プライスアクション → トリガー。"""
    if df_short is None or len(df_short) < lookback:
        return None
    win = df_short.tail(lookback).reset_index(drop=True)
    highs = win["High"].values
    lows = win["Low"].values
    closes = win["Close"].values
    opens = win["Open"].values
    n = len(win)

    broke_idx = None
    for i in range(n - 4):
        if lows[i] < pdl * 0.9997:
            broke_idx = i
            break
    if broke_idx is None:
        return None

    post = win.iloc[broke_idx + 1:]
    if post.empty:
        return None
    retest_hit = False
    retest_idx = None
    for j, hv in enumerate(post["High"].values):
        if abs(hv - pdl) / pdl < 0.0015:
            retest_hit = True
            retest_idx = broke_idx + 1 + j
            break
    if not retest_hit:
        return None

    flag_slice = win.iloc[max(retest_idx, n - 7): n - 1]
    if len(flag_slice) < 2:
        return None
    fh = flag_slice["High"].values
    fl = flag_slice["Low"].values
    asc_high = sum(1 for i in range(1, len(fh)) if fh[i] >= fh[i - 1] * 0.9995)
    asc_low = sum(1 for i in range(1, len(fl)) if fl[i] >= fl[i - 1] * 0.9995)
    flag_ok = asc_high >= max(1, len(fh) - 2) and asc_low >= max(1, len(fl) - 2)
    flag_lower = float(fl.min())

    last = win.iloc[-1]
    prev = win.iloc[-2]
    body = abs(last["Close"] - last["Open"]) or 1e-9
    rng = last["High"] - last["Low"] or 1e-9
    upper_wick = last["High"] - max(last["Open"], last["Close"])
    pin_bar = (upper_wick / rng) > 0.5 and last["Close"] <= last["Open"]
    engulf = (
        prev["Close"] > prev["Open"]
        and last["Close"] < last["Open"]
        and last["Close"] <= prev["Open"]
        and last["Open"] >= prev["Close"]
    )

    trigger = last["Close"] < flag_lower and last["Close"] < last["Open"]

    return {
        "broke": True,
        "broke_idx": int(broke_idx),
        "retest": True,
        "retest_idx": int(retest_idx),
        "flag": flag_ok,
        "pa_pin": bool(pin_bar),
        "pa_engulf": bool(engulf),
        "trigger": bool(trigger),
        "flag_lower": flag_lower,
        "flag_upper": float(fh.max()),
    }


# ================== フィルター ==================

def _no_trade_zone(price: float, pdh: float, pdl: float, df_short: pd.DataFrame) -> bool:
    """ノートレードゾーン判定。

    元手法:
      - 前日高値 と プレマーケット安値 の間
      - 前日安値 と プレマーケット高値 の間
    FX には厳密なプレマーケットが無いため、直近『当日相当』
    (= 最新 32 本 = 約8時間) の高値・安値で代替する。
    """
    if df_short is None or len(df_short) < 32:
        return False
    session = df_short.tail(32)
    pm_low = float(session["Low"].min())
    pm_high = float(session["High"].max())

    # pdh と pm_low に挟まれた狭いゾーン
    if pdl < price < pdh:
        # かつ price が pm_low と pdh の間 / pm_high と pdl の間 いずれかに収まる
        if pm_low <= price <= pdh or pdl <= price <= pm_high:
            # さらに幅が小さければ (0.4%以下) ノートレード
            width = (pdh - pdl) / max(price, 1e-9)
            if width < 0.006:
                return True
    return False


def _smt_alignment(pair: str, direction: str, all_pairs_context: dict) -> tuple[int, Optional[str]]:
    """簡易 SMT ダイバージェンス評価 (FX 用)。

    all_pairs_context: {pair: last_return_pct} 全ペア直近リターン。
    JPY クロス同士、USD メジャー同士で同方向に動いているかを確認する。
    不整合があれば減点+warning。

    Returns: (加点 -5 〜 +5, warning 文字列 or None)
    """
    if not all_pairs_context:
        return 0, None

    # 対象ペアのベース/クォートを抽出
    try:
        base, quote = pair.split("/")
    except ValueError:
        return 0, None

    # 同グループ (ベースまたはクォートが一致) のペアを拾う
    peers = []
    for p, chg in all_pairs_context.items():
        if p == pair:
            continue
        try:
            b, q = p.split("/")
        except ValueError:
            continue
        if b == base or q == quote or b == quote or q == base:
            peers.append((p, chg))

    if not peers:
        return 0, None

    own = all_pairs_context.get(pair, 0.0)
    # direction == long → own > 0 を期待
    same_sign = sum(1 for _, c in peers if (own > 0 and c > 0) or (own < 0 and c < 0))
    ratio = same_sign / len(peers)
    if ratio >= 0.6:
        return 5, None
    if ratio <= 0.3:
        return -5, f"SMT不一致: 関連ペアの{int((1 - ratio) * 100)}%が逆方向に動いている"
    return 0, None


# ================== メイン ==================

def _empty_signal_dict(pair: str, symbol: str, reasons=None) -> dict:
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
        "pdh": None,
        "pdl": None,
    }


def analyze_pair_pdhl(
    pair: str,
    symbol: str,
    df_long: pd.DataFrame,
    df_mid: pd.DataFrame,
    df_short: pd.DataFrame,
    all_pairs_context: Optional[dict] = None,
    alert_threshold: int = 75,
) -> dict:
    """PDH/PDL ブレイクアウト・リテスト手法の判定。

    戻り値は strategy.Signal を dict 化したのとほぼ同形式。
    ただし entry_type は "pdhl_long_retest" / "pdhl_short_retest" / "wait" / "none"。
    """
    if df_long is None or df_short is None:
        return _empty_signal_dict(pair, symbol, ["データ取得失敗 (PDHL)"])
    if len(df_long) < 3 or len(df_short) < 40:
        return _empty_signal_dict(
            pair, symbol,
            [f"データ不足 (日足={len(df_long) if df_long is not None else 0} 15M={len(df_short) if df_short is not None else 0})"],
        )

    pdh, pdl = _get_pdh_pdl(df_long)
    if pdh is None or pdl is None:
        return _empty_signal_dict(pair, symbol, ["前日高値/安値取得失敗"])

    price = _safe_float(df_short["Close"].iloc[-1], 0.0)

    result = _empty_signal_dict(pair, symbol)
    result["price"] = price
    result["pdh"] = pdh
    result["pdl"] = pdl
    result["reasons"].append(f"前日高値 PDH={pdh:.5f} / 前日安値 PDL={pdl:.5f}")

    # ---- ノートレードゾーン判定 ----
    if _no_trade_zone(price, pdh, pdl, df_short):
        result["reasons"].append("ノートレードゾーン: PDH-PDL 間の狭い領域 → 見送り")
        result["entry_type"] = "wait"
        return result

    # ---- ロング / ショート セットアップ検出 ----
    long_setup = _detect_long_setup(pdh, df_short)
    short_setup = _detect_short_setup(pdl, df_short)

    direction = "none"
    setup = None
    if long_setup and short_setup:
        # 稀に両方検出された場合はより新しい側を優先 (broke_idx が大きい方)
        if long_setup.get("broke_idx", 0) >= short_setup.get("broke_idx", 0):
            direction = "long"
            setup = long_setup
        else:
            direction = "short"
            setup = short_setup
    elif long_setup:
        direction = "long"
        setup = long_setup
    elif short_setup:
        direction = "short"
        setup = short_setup

    if not setup:
        result["reasons"].append("PDH/PDL ブレイク+リテスト未検出 (待機)")
        result["entry_type"] = "wait"
        return result

    result["direction"] = direction
    result["entry_type"] = (
        "pdhl_long_retest" if direction == "long" else "pdhl_short_retest"
    )

    # ---- スコアリング ----
    score = 0

    # a) ブレイク成立: 25
    score += 25
    result["reasons"].append(
        f"{'PDH' if direction == 'long' else 'PDL'} を明確にブレイク"
    )

    # b) リテスト成立: 20
    score += 20
    result["reasons"].append(
        f"{'PDH' if direction == 'long' else 'PDL'} 付近へのリテスト完了 (ダマシ回避)"
    )

    # c) フラッグ形成: 15
    if setup["flag"]:
        score += 15
        result["reasons"].append(
            f"15M で{'ブル' if direction == 'long' else 'ベア'}フラッグ形成"
        )
    else:
        result["reasons"].append("フラッグ形成が不完全")

    # d) プライスアクション: 15 (pin=8, engulf=12, 両方=15)
    pa_pts = 0
    pa_labels = []
    if setup["pa_pin"]:
        pa_pts = max(pa_pts, 8)
        pa_labels.append("長い{}ヒゲ".format("下" if direction == "long" else "上"))
    if setup["pa_engulf"]:
        pa_pts = max(pa_pts, 12)
        pa_labels.append("{}の包み足".format("陽" if direction == "long" else "陰"))
    if setup["pa_pin"] and setup["pa_engulf"]:
        pa_pts = 15
    score += pa_pts
    if pa_labels:
        result["reasons"].append("プライスアクション: " + " + ".join(pa_labels))
    else:
        result["reasons"].append("プライスアクション未確認")

    # e) フラッグブレイク = 15Mトリガー: 20
    if setup["trigger"]:
        score += 20
        result["reasons"].append(
            "★フラッグ{}ブレイク (エントリートリガー点灯)".format(
                "上限" if direction == "long" else "下限"
            )
        )
    else:
        result["reasons"].append("フラッグブレイク未発生 (トリガー待機)")

    # f) SMT 整合: ±5
    smt_pts, smt_warn = _smt_alignment(pair, direction, all_pairs_context or {})
    score += smt_pts
    if smt_pts > 0:
        result["reasons"].append("SMT整合: 関連ペアも同方向")
    if smt_warn:
        result["warnings"].append(smt_warn)

    # ---- SL / TP (リスクリワード目安) ----
    if direction == "long":
        sl_base = min(setup.get("flag_lower", pdh), pdh)
        result["stop_loss"] = sl_base * 0.9985
        # 直近高値探索 (win の max)
        recent_high = float(df_short["High"].tail(80).max())
        result["take_profit"] = max(recent_high, price + (price - result["stop_loss"]))
    else:
        sl_base = max(setup.get("flag_upper", pdl), pdl)
        result["stop_loss"] = sl_base * 1.0015
        recent_low = float(df_short["Low"].tail(80).min())
        result["take_profit"] = min(recent_low, price - (result["stop_loss"] - price))

    result["score"] = min(int(score), 100)
    result["has_trigger"] = bool(setup["trigger"])
    # アラート条件: トリガー発火 + 閾値超過
    result["is_alert"] = (
        result["has_trigger"]
        and result["score"] >= alert_threshold
        and direction != "none"
    )

    # トリガー未発生ならスコアを閾値未満にキャップ (既存ORZ方針と揃える)
    if not result["has_trigger"]:
        result["score"] = min(result["score"], alert_threshold - 5)

    return result
