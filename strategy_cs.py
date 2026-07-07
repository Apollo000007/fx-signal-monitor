"""CS — Currency Strength (通貨強弱) 手法。

設計思想 (R2 実トレード分析に基づく):
  6週間の実トレードで唯一の明確な勝ち筋は「USD順張りのドルストレート」
  (14勝4敗 +909)。= 「強い通貨を買い、弱い通貨を売る」を全通貨に一般化する。

ルール (機械的):
  1. 通貨強弱: 全監視ペアの日足から 8 通貨 (USD/EUR/JPY/GBP/AUD/NZD/CAD/CHF)
     の強弱スコアを算出 (20日+5日モメンタムの合成、ペア横断平均)。
  2. 対象: ペアの base が上位2位以内 かつ quote が下位2位以内 → long 候補
            (逆なら short 候補)。「最強 vs 最弱」の組合せのみ。
  3. トレンド一致: 日足+4H の analyze_timeframe が候補方向と一致 (MTF と同基準)。
  4. 15M トリガー: S/A ランクのパターン (A は重要節目必須、MTF と同じ)。
  5. SL = パターン構造 (1R) / TP = 3R。api 側で最低2R床。
  6. EVゲート: バックテスト計測後は +EV 実証ペアのみ alert (mtf と同方式)。

通貨強弱の計算にはペア横断の日足が必要なため、呼び出し側が
ctx_daily = {pair_label: df_long} を渡す (api は全ペア分、backtest は時点スライス)。
戻り値は strategy_pa / strategy_mtf と同じ dict 形式。
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from strategy import analyze_timeframe
from strategy_pa import _key_levels, _near_level
import patterns as pat

_RANK_BASE = {"S": 50, "A": 40}
TOP_N = 2          # base が上位N位以内
BOTTOM_N = 2       # quote が下位N位以内
LOOKBACK_LONG = 20   # 日足モメンタム (主)
LOOKBACK_SHORT = 5   # 日足モメンタム (直近)


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


def currency_strength(ctx_daily: dict) -> dict[str, float]:
    """{pair_label: df_daily} → {通貨: 強弱スコア%}。

    各ペアの 20日/5日 リターンを、base には + / quote には − で配分し、
    通貨ごとに平均する (0.7*20日 + 0.3*5日 の合成)。
    """
    votes: dict[str, list] = {}
    for label, df in (ctx_daily or {}).items():
        if df is None or len(df) < LOOKBACK_LONG + 2 or "/" not in label:
            continue
        base, quote = label.split("/", 1)
        c = df["Close"]
        c0 = _safe(c.iloc[-1])
        cl = _safe(c.iloc[-1 - LOOKBACK_LONG])
        cs = _safe(c.iloc[-1 - LOOKBACK_SHORT])
        if c0 <= 0 or cl <= 0 or cs <= 0:
            continue
        mom = 0.7 * ((c0 - cl) / cl * 100.0) + 0.3 * ((c0 - cs) / cs * 100.0)
        votes.setdefault(base, []).append(+mom)
        votes.setdefault(quote, []).append(-mom)
    return {ccy: sum(v) / len(v) for ccy, v in votes.items() if v}


def analyze_pair_cs(
    pair: str,
    symbol: str,
    df_long: pd.DataFrame,
    df_mid: pd.DataFrame,
    df_short: pd.DataFrame,
    ctx_daily: Optional[dict] = None,
    alert_threshold: int = 75,
) -> dict:
    """通貨強弱手法の判定 (dict を返す)。"""
    if df_short is None or len(df_short) < 30:
        return _empty(pair, symbol, ["データ不足 (CS 15M)"])
    if df_long is None or df_mid is None or len(df_long) < 60 or len(df_mid) < 60:
        return _empty(pair, symbol, ["データ不足 (CS HTF)"])
    if "/" not in pair:
        return _empty(pair, symbol, ["ペア形式不正 (CS)"])

    result = _empty(pair, symbol)
    df_eval = df_short.iloc[:-1] if len(df_short) >= 2 else df_short
    price = _safe(df_eval["Close"].iloc[-1])
    result["price"] = price

    # ---- 1) 通貨強弱ランキング ----
    strength = currency_strength(ctx_daily or {})
    if len(strength) < 6:
        return _empty(pair, symbol, ["通貨強弱の算出に必要なペアデータ不足 (CS)"])
    ranked = sorted(strength.items(), key=lambda kv: kv[1], reverse=True)
    order = [c for c, _ in ranked]
    base, quote = pair.split("/", 1)
    if base not in order or quote not in order:
        return _empty(pair, symbol, [f"{pair} の通貨が強弱表に無い (CS)"])
    bi, qi = order.index(base), order.index(quote)
    n = len(order)
    top3 = " > ".join(f"{c}({v:+.1f})" for c, v in ranked[:3])
    bot3 = " < ".join(f"{c}({v:+.1f})" for c, v in ranked[-3:][::-1])
    result["reasons"].append(f"通貨強弱: 強 {top3} … 弱 {bot3}")

    direction = None
    if bi < TOP_N and qi >= n - BOTTOM_N:
        direction = "long"    # 最強を買い / 最弱を売る
    elif qi < TOP_N and bi >= n - BOTTOM_N:
        direction = "short"
    if direction is None:
        result["entry_type"] = "wait"
        result["reasons"].append(
            f"{base}({bi+1}位)/{quote}({qi+1}位) — 最強×最弱の組合せでない (見送り)"
        )
        return result

    label = "買い" if direction == "long" else "売り"
    result["reasons"].append(
        f"★{base}({bi+1}位) vs {quote}({qi+1}位) — 強弱明確、{pair} {label}候補 (+30)"
    )
    score = 30

    # ---- 2) 日足+4H トレンド一致 (方向フィルタ) ----
    try:
        d_dir = analyze_timeframe(df_long).direction   # up/down/range
        m_dir = analyze_timeframe(df_mid).direction
    except Exception:
        return _empty(pair, symbol, ["トレンド判定エラー (CS)"])
    want = "up" if direction == "long" else "down"
    if d_dir != want or m_dir != want:
        result["entry_type"] = "wait"
        result["reasons"].append(
            f"日足({d_dir})/4H({m_dir}) が強弱方向({want})と不一致 — 見送り"
        )
        return result
    result["direction"] = direction
    result["entry_type"] = f"cs_{direction}"
    result["reasons"].append("★日足+4H トレンドも強弱方向と一致 (+25)")
    score += 25

    # ---- 3) 15M S/A パターン (A は重要節目必須) ----
    levels = _key_levels(df_long, df_eval, symbol)
    tol = 0.0010 if "JPY" in symbol.upper() else 0.0008
    level_hit = _near_level(price, levels, tol)
    at_level = level_hit is not None

    cands = []
    for m in pat.detect(df_eval):
        if m.get("sig") != direction:
            continue
        rk = pat.rank_of(m.get("key", ""))
        if rk == "S" or (rk == "A" and at_level):
            cands.append(m)
    if not cands:
        result["reasons"].append("15Mトリガー待ち (S、またはA+重要節目)")
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
    score += _RANK_BASE.get(rank, 40)
    score += int(round(best.get("strength", 0.0) * 10))
    result["reasons"].append(
        f"★15M【{rank}】{meta.get('name', key)} ({meta.get('en','')})"
    )
    if at_level:
        score += 8
        result["reasons"].append(f"→ 重要節目: {level_hit[0]} {level_hit[1]:.5f} (+8)")
    if meta.get("fk"):
        result["warnings"].append(f"ダマシ注意: {meta['fk']}")

    # ---- 4) SL / TP ----
    sl_hint = best.get("sl_hint")
    if sl_hint is None or sl_hint <= 0:
        result["entry_type"] = "wait"
        result["reasons"].append("構造的SLを取れない — 見送り")
        result["score"] = min(score, alert_threshold - 5)
        return result
    buf = price * (0.0010 if "JPY" in symbol.upper() else 0.0008)
    sl = (sl_hint - buf) if direction == "long" else (sl_hint + buf)
    r = abs(price - sl)
    if r <= 0 or (direction == "long" and sl >= price) or (direction == "short" and sl <= price):
        result["entry_type"] = "wait"
        result["reasons"].append("SL整合せず — 見送り")
        result["score"] = min(score, alert_threshold - 5)
        return result
    tp = price + 3.0 * r if direction == "long" else price - 3.0 * r
    result["stop_loss"] = sl
    result["take_profit"] = tp
    result["reasons"].append(f"SL={sl:.5f} (構造=1R) / TP={tp:.5f} (固定3R)")

    result["score"] = min(int(score), 100)
    result["is_alert"] = bool(
        result["has_trigger"] and result["score"] >= alert_threshold
    )
    return result
