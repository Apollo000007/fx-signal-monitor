"""PA — Price Action / ローソク足パターン手法。

出典: docs/candlestick_patterns_reference.html
設計思想 (= reference HTML の「大前提」をハードゲート化):
  ① 確定足のみ      : 進行中バーで判定しない (評価足 = iloc[-2], 確認足 = iloc[-1])
  ② 上位足順方向    : 日足+4H 50EMA バイアスと同方向のみ (逆張りは捨てる)
  ③ 重要な節目      : PDH/PDL / スイング S/R / SMA20·50 / キリ番 に重なる時のみ
  ④ 次足確認        : 確認足がシグナル方向に確定して初めて成立
  ⑤ 資金管理        : SL=パターン構造(1R) / TP=固定3R (低勝率でも +EV)
  + ランクゲート     : S/A のみアラート (B=内部スコア / C=文脈のみ)
  + 指標リスク抑制   : 当日リスク★高 / 対象通貨の高重要イベント近接で抑制
  + EV ホワイトリスト: backtest で +EV と確認できた pair×pattern のみ is_alert

戻り値は strategy_dtp と同じ dict 形式 (+ pattern / rank / pattern_name)。
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from indicators import ema, slope, sma, find_swings, cluster_levels
import patterns as pat

ROOT = Path(__file__).resolve().parent
WHITELIST_FILE = ROOT / "state" / "pa_whitelist.json"
CALENDAR_CACHE = ROOT / "state" / "calendar_cache.json"

_RANK_BASE = {"S": 55, "A": 45, "B": 35, "C": 15}


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


# ============== サブ判定 ==============

def _htf_bias(df_long: pd.DataFrame, df_mid: pd.DataFrame) -> tuple[str, list]:
    """日足 50EMA と 4H 50EMA の傾斜が両方一致したときのみ方向を返す
    (strategy_dtp._htf_bias と同方式)。"""
    reasons: list = []
    if df_long is None or df_mid is None:
        return "none", reasons
    if len(df_long) < 60 or len(df_mid) < 60:
        return "none", reasons
    d_ema = ema(df_long["Close"], 50)
    m_ema = ema(df_mid["Close"], 50)
    d_slope = slope(d_ema, 5)
    m_slope = slope(m_ema, 5)
    d_c = _safe(df_long["Close"].iloc[-1])
    m_c = _safe(df_mid["Close"].iloc[-1])
    d_e = _safe(d_ema.iloc[-1], d_c)
    m_e = _safe(m_ema.iloc[-1], m_c)
    up = (d_slope > 0.02 and m_slope > 0.02 and d_c > d_e and m_c > m_e)
    dn = (d_slope < -0.02 and m_slope < -0.02 and d_c < d_e and m_c < m_e)
    if up:
        reasons.append(f"日足/4H 両 50EMA 上向き (D:{d_slope:+.2f}% 4H:{m_slope:+.2f}%) — 上昇トレンド一致")
        return "long", reasons
    if dn:
        reasons.append(f"日足/4H 両 50EMA 下向き (D:{d_slope:+.2f}% 4H:{m_slope:+.2f}%) — 下降トレンド一致")
        return "short", reasons
    reasons.append("日足/4H のトレンド不一致 — PA 見送り")
    return "none", reasons


def _key_levels(df_long: pd.DataFrame, df_short: pd.DataFrame, symbol: str) -> list[tuple[str, float]]:
    """重要節目の候補 (ラベル, 価格) を集める。"""
    levels: list[tuple[str, float]] = []
    # 前日高安 (日足の 1 本前)
    if df_long is not None and len(df_long) >= 2:
        levels.append(("前日高値", _safe(df_long["High"].iloc[-2])))
        levels.append(("前日安値", _safe(df_long["Low"].iloc[-2])))
    if df_short is not None and len(df_short) >= 60:
        sh, sl = find_swings(df_short.tail(120), window=3)
        for v in cluster_levels([p for _, p in sh[-12:]]):
            levels.append(("スイング抵抗", v))
        for v in cluster_levels([p for _, p in sl[-12:]]):
            levels.append(("スイング支持", v))
        s20 = sma(df_short["Close"], 20)
        s50 = sma(df_short["Close"], 50)
        levels.append(("15M SMA20", _safe(s20.iloc[-1])))
        levels.append(("15M SMA50", _safe(s50.iloc[-1])))
        # キリ番 (JPY=0.50 刻み / その他=0.0050 刻み)
        c = _safe(df_short["Close"].iloc[-1])
        step = 0.5 if "JPY" in symbol.upper() else 0.005
        if c > 0:
            near = round(c / step) * step
            levels.append(("キリ番", near))
    return [(lbl, v) for lbl, v in levels if v and v > 0]


def _near_level(price: float, levels: list[tuple[str, float]], tol_pct: float) -> Optional[tuple[str, float]]:
    best = None
    for lbl, v in levels:
        d = abs(price - v) / price if price else 1.0
        if d <= tol_pct and (best is None or d < best[2]):
            best = (lbl, v, d)
    return (best[0], best[1]) if best else None


def _in_session(df_short: pd.DataFrame) -> tuple[bool, str]:
    if df_short is None or len(df_short) == 0:
        return False, ""
    ts = df_short.index[-1]
    try:
        hour = ts.tz_convert("UTC").hour if ts.tzinfo else ts.hour
    except Exception:
        hour = getattr(ts, "hour", 12)
    if 7 <= hour < 21:
        return True, f"{hour:02d}:00 UTC (ロンドン/NY)"
    return False, f"{hour:02d}:00 UTC (時間外)"


# ============== EV ホワイトリスト ==============

_wl_cache: dict = {"mtime": None, "data": None}


def _load_whitelist() -> Optional[dict]:
    """state/pa_whitelist.json を mtime キャッシュ付きで読む。

    形式: {"min_n":20, "entries": {"USD/JPY|engulf_bull": {...}, ...}}
    不在 → None (ブートストラップ: S ランクのみ許可)。
    """
    try:
        st = WHITELIST_FILE.stat()
    except OSError:
        return None
    if _wl_cache["mtime"] != st.st_mtime:
        try:
            _wl_cache["data"] = json.loads(WHITELIST_FILE.read_text(encoding="utf-8"))
            _wl_cache["mtime"] = st.st_mtime
        except Exception:
            return None
    return _wl_cache["data"]


def _is_whitelisted(pair: str, key: str, rank: str) -> tuple[bool, str]:
    wl = _load_whitelist()
    if not wl or not wl.get("entries"):
        # ブートストラップ: バックテスト前は最も信頼度の高い S のみ通す
        if rank == "S":
            return True, "EV未検証 (S ランクのみ暫定許可)"
        return False, "EVホワイトリスト未生成 (S以外は保留)"
    if f"{pair}|{key}" in wl["entries"]:
        e = wl["entries"][f"{pair}|{key}"]
        return True, f"EV実証済 (n={e.get('n')} WR{e.get('wr')}% PF{e.get('pf')} EV{e.get('ev')}R)"
    return False, "このペアでEV+未確認のパターン (アラート保留)"


# ============== 指標リスク抑制 ==============

def _news_suppress(pair: str) -> tuple[bool, str]:
    """当日リスク★が高い / 対象通貨に高重要イベントが近接 → 抑制。

    calendar_cache.json が無ければ抑制しない (フェイルオープン)。
    """
    try:
        cal = json.loads(CALENDAR_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return False, ""
    risk = cal.get("risk", {})
    stars = int(risk.get("stars", 1) or 1)
    ccy = {p.strip().upper() for p in pair.split("/")}
    # 当日リスク 4★以上は全 PA 抑制 (HTML: 指標集中日はパターン無効化)
    if stars >= 4:
        return True, f"当日相場リスク {stars}★ ({risk.get('level','')}) — PA アラート抑制"
    # 対象通貨の本日 High イベントがある日は慎重化 (抑制)
    for ev in cal.get("events", []):
        if ev.get("is_today") and ev.get("impact") == "High" and str(ev.get("currency", "")).upper() in ccy:
            return True, f"本日 {ev.get('currency')} 高重要指標あり ({ev.get('jst_time')} {ev.get('title','')}) — PA 抑制"
    return False, ""


# ============== メイン ==============

def analyze_pair_pa(
    pair: str,
    symbol: str,
    df_long: pd.DataFrame,
    df_mid: pd.DataFrame,
    df_short: pd.DataFrame,
    alert_threshold: int = 75,
) -> dict:
    """ローソク足パターン手法の判定 (dict を返す)。"""
    if df_short is None or len(df_short) < 40:
        return _empty(pair, symbol, ["データ不足 (PA 15M)"])
    if df_long is None or df_mid is None or len(df_long) < 60 or len(df_mid) < 60:
        return _empty(pair, symbol, ["データ不足 (PA HTF)"])

    # 確定足を最終行に: 評価足 = iloc[-2], 確認足 = iloc[-1]
    df_eval = df_short.iloc[:-1]          # 末尾 = 評価足 (確定済み)
    confirm = df_short.iloc[-1]           # 次足 (確認用)
    price = _safe(df_short["Close"].iloc[-2])  # 評価足の終値 = エントリー基準
    result = _empty(pair, symbol)
    result["price"] = price

    # --- ② 上位足バイアス ---
    direction, bias_reasons = _htf_bias(df_long, df_mid)
    result["reasons"].extend(bias_reasons)
    if direction == "none":
        result["entry_type"] = "wait"
        return result

    # --- パターン検出 (評価足) ---
    matches = pat.detect(df_eval)
    # 方向一致 (順張り) のみ採用
    aligned = [m for m in matches if m["sig"] == direction]
    if not aligned:
        result["direction"] = direction
        result["entry_type"] = "wait"
        result["reasons"].append("上位足方向に一致するローソク足パターンなし — 見送り")
        return result

    # 最良 = ランク→strength
    aligned.sort(key=lambda m: (pat.RANK_ORDER.get(pat.rank_of(m["key"]), 0), m["strength"]), reverse=True)
    best = aligned[0]
    key = best["key"]
    rank = pat.rank_of(key)
    meta = pat.meta_of(key)
    result["direction"] = direction
    result["pattern"] = key
    result["rank"] = rank
    result["pattern_name"] = meta.get("name", key)
    result["entry_type"] = f"pa_{key}_{'long' if direction == 'long' else 'short'}"
    result["reasons"].append(f"【{rank}】{meta.get('name', key)} ({meta.get('en','')}) 検出 — {meta.get('m','')}")

    score = _RANK_BASE.get(rank, 15)

    # --- ② 方向一致ボーナス ---
    score += 15
    result["reasons"].append("→ 上位足トレンド順方向 (+15)")

    # --- ③ 重要な節目 ---
    levels = _key_levels(df_long, df_short, symbol)
    tol = 0.0010 if "JPY" in symbol.upper() else 0.0008
    hit = _near_level(price, levels, tol)
    at_level = hit is not None
    if at_level:
        score += 18
        result["reasons"].append(f"→ 重要節目に重なる: {hit[0]} {hit[1]:.5f} (+18)")
    else:
        result["reasons"].append("重要節目から離れている — 信頼度低下")
        result["warnings"].append("節目でない位置のパターン (HTML大前提③ 未充足)")

    # --- ④ 次足確認 ---
    cc = _safe(confirm["Close"])
    co = _safe(confirm["Open"])
    if direction == "long":
        confirmed = cc > co and cc > price
    else:
        confirmed = cc < co and cc < price
    if confirmed:
        score += 12
        result["reasons"].append("→ 次足がシグナル方向に確定 (+12)")
    else:
        result["reasons"].append("次足確認待ち (反転方向に確定せず)")

    # --- 確信度 (strength) / セッション ---
    score += int(round(best["strength"] * 10))
    in_sess, sess_txt = _in_session(df_short)
    if in_sess:
        score += 5
        result["reasons"].append(f"取引時間内 {sess_txt} (+5)")
    else:
        result["warnings"].append(f"取引時間外 {sess_txt} — 流動性注意")

    # ダマシ注意 (HTML fk)
    if meta.get("fk"):
        result["warnings"].append(f"ダマシ注意: {meta['fk']}")

    # --- ⑤ SL / TP (構造SL=1R, 固定3R) ---
    sl_hint = best.get("sl_hint")
    if sl_hint is None or sl_hint <= 0:
        result["entry_type"] = "wait"
        result["reasons"].append("構造的 SL を取れないパターン — 見送り")
        return result
    buf = price * (0.0010 if "JPY" in symbol.upper() else 0.0008)
    sl = (sl_hint - buf) if direction == "long" else (sl_hint + buf)
    r = abs(price - sl)
    if r <= 0 or (direction == "long" and sl >= price) or (direction == "short" and sl <= price):
        result["entry_type"] = "wait"
        result["reasons"].append("SL 整合せず — 見送り")
        return result
    tp = price + 3.0 * r if direction == "long" else price - 3.0 * r
    result["stop_loss"] = sl
    result["take_profit"] = tp
    result["reasons"].append(f"SL={sl:.5f} (パターン構造=1R) / TP={tp:.5f} (固定3R)")

    # --- ランクゲート + EV ホワイトリスト + 指標リスク ---
    sa = rank in ("S", "A")
    wl_ok, wl_msg = _is_whitelisted(pair, key, rank)
    result["reasons"].append(wl_msg)
    news_block, news_msg = _news_suppress(pair)
    if news_msg:
        result["warnings"].append(news_msg)

    has_trigger = bool(sa and at_level and confirmed)
    result["has_trigger"] = has_trigger

    score = min(int(score), 100)
    result["score"] = score

    # 発見モード (scripts/backtest_pa.py): EV ホワイトリスト/指標抑制を外し、
    # 純粋なパターン機構の +EV を測る (whitelist の循環依存を回避)。
    discovery = os.environ.get("PA_BACKTEST_DISCOVERY") == "1"
    if discovery:
        result["is_alert"] = bool(
            has_trigger and score >= alert_threshold and direction != "none"
        )
    else:
        result["is_alert"] = bool(
            has_trigger
            and wl_ok
            and (not news_block)
            and score >= alert_threshold
            and direction != "none"
        )

    # トリガー未充足はスコアを閾値未満にキャップ (他手法と整合)
    if not has_trigger or (not wl_ok and not discovery):
        result["score"] = min(result["score"], alert_threshold - 5)

    return result
