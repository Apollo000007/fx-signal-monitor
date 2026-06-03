"""リスクリワード(RR)ポリシの単一ソース。

2週間デモの所見: 旧 PDHL は TP=entry±1R(1:1)、勝率50%×1:1 でスプレッド負け。
本モジュールで「利確は最低 2R」を全シグナルに保証する。

- min_rr_tp(): 構造的 TP が 2R より遠ければそれを採用、近ければ 2R まで引き上げ。
  → signals.json / Telegram / paper / MT5 の実値まで ≥2R が反映される。
- フロントの frontend/src/lib/mm.ts::computeMMLevels と同じ式 (DEFAULT_MIN_RR=2.0)。

strategy*.py の SL/方向/トリガー判定は一切変更しない。TP の床のみ後段で適用する。
"""
from __future__ import annotations

from typing import Optional

DEFAULT_MIN_RR = 2.0   # 最低リスクリワード (= mm.ts と一致)
RECOMMENDED_RR = 3.0   # 推奨利確 (損小利大の伸ばし目標)


def r_multiple(price, sl, tp, direction: str) -> Optional[float]:
    """TP の実効リスクリワード (reward/risk)。算出不能なら None。"""
    try:
        if price is None or sl is None or tp is None:
            return None
        risk = abs(float(price) - float(sl))
        if risk <= 0:
            return None
        # 方向整合 (long は tp>price, short は tp<price) でなければ無効
        if direction == "long" and not (float(tp) > float(price)):
            return None
        if direction == "short" and not (float(tp) < float(price)):
            return None
        return abs(float(tp) - float(price)) / risk
    except (TypeError, ValueError):
        return None


def min_rr_tp(price, sl, tp, direction: str, min_rr: float = DEFAULT_MIN_RR):
    """利益側に最低 min_rr の床を適用した TP を返す。

    - price/sl が無い、または r<=0 → tp をそのまま返す (床適用不可)。
    - 構造的 tp が無い → entry ± min_rr×R を返す。
    - 構造的 tp がある → long: max(tp, 2R) / short: min(tp, 2R) (利益側に遠い方)。
    direction が long/short 以外なら tp をそのまま返す。
    """
    try:
        if price is None or sl is None or direction not in ("long", "short"):
            return tp
        p = float(price)
        s = float(sl)
        r = abs(p - s)
        if r <= 0:
            return tp
        floor = p + min_rr * r if direction == "long" else p - min_rr * r
        if tp is None:
            return floor
        t = float(tp)
        if direction == "long":
            return max(t, floor)
        return min(t, floor)
    except (TypeError, ValueError):
        return tp


def rr_target(price, sl, direction: str, rr: float):
    """entry ± rr×R の価格 (推奨3Rライン等)。算出不能なら None。"""
    try:
        if price is None or sl is None or direction not in ("long", "short"):
            return None
        p = float(price)
        r = abs(p - float(sl))
        if r <= 0:
            return None
        return p + rr * r if direction == "long" else p - rr * r
    except (TypeError, ValueError):
        return None
