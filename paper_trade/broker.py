"""仮想ブローカー: ライブシグナルでの open/close を JSON ファイルに永続化。

設計:
  - state/paper_positions.json   オープン中のポジション (常時 5 件前後の想定)
  - state/paper_history.json     クローズ済みトレード履歴 (追記のみ)

トレード成立ルール (backtest engine と統一):
  - エントリー: is_alert=True 時の signal.price で約定 (cron 走行時の最新値)
  - 決済    : SL/TP のうち先に到達した方で約定 (15M バーの OHLC で判定)
              同一バーで両方 hit なら SL 採用 (保守的)
  - 重複    : 同一 pair に open 中があれば新規 alert 無視
  - スプレッド: JPY クロス 1 pip、その他 0.5 pip
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional

import pandas as pd


def is_jpy_cross(pair: str) -> bool:
    return "/JPY" in pair


def pip_size(pair: str) -> float:
    return 0.01 if is_jpy_cross(pair) else 0.0001


def spread_price(pair: str) -> float:
    return (1.0 if is_jpy_cross(pair) else 0.5) * pip_size(pair)


@dataclass
class PaperPosition:
    """オープン中ポジション。"""
    id: str                # uuid 風: f"{pair}-{method}-{opened_ts}"
    pair: str
    method: str
    direction: str         # "long" / "short"
    entry_type: str
    entry_time: str        # ISO
    entry_price: float
    stop_loss: float
    take_profit: float
    score: int
    last_check_time: Optional[str] = None  # 最後に SL/TP チェックした時刻

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "PaperPosition":
        return PaperPosition(**d)


@dataclass
class PaperTrade:
    """クローズ済みトレード。"""
    id: str
    pair: str
    method: str
    direction: str
    entry_type: str
    entry_time: str
    entry_price: float
    stop_loss: float
    take_profit: float
    score: int
    exit_time: str
    exit_price: float
    exit_reason: str       # "sl" / "tp" / "sl_tp_ambiguous"
    pnl_pips: float
    pnl_r: float           # R-multiple

    def to_dict(self) -> dict:
        return asdict(self)


# ============== ファイル I/O ==============

def load_positions(path: Path) -> list[PaperPosition]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [PaperPosition.from_dict(d) for d in raw]
    except Exception:
        return []


def save_positions(path: Path, positions: list[PaperPosition]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([p.to_dict() for p in positions], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_history(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def append_history(path: Path, trade: PaperTrade):
    path.parent.mkdir(parents=True, exist_ok=True)
    history = load_history(path)
    history.append(trade.to_dict())
    path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


# ============== ロジック ==============

def open_position(
    pair: str, method: str, direction: str, entry_type: str,
    entry_price: float, stop_loss: float, take_profit: float, score: int,
    now: pd.Timestamp,
) -> PaperPosition:
    """新規ポジションを生成。"""
    ts_str = now.isoformat()
    pid = f"{pair}-{method}-{int(now.timestamp())}"
    return PaperPosition(
        id=pid,
        pair=pair,
        method=method,
        direction=direction,
        entry_type=entry_type,
        entry_time=ts_str,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        score=score,
        last_check_time=ts_str,
    )


def check_exit(
    pos: PaperPosition,
    df_short: pd.DataFrame,
) -> Optional[PaperTrade]:
    """ポジションの SL/TP 到達を直近の 15M バーで判定。

    last_check_time 以降のバーで:
      - long  : Low <= SL なら SL hit、High >= TP なら TP hit
      - short : High >= SL なら SL hit、Low <= TP なら TP hit
      - 両方 hit のバーは SL 優先 (保守的)
    """
    if df_short is None or df_short.empty:
        return None

    last_check = pd.Timestamp(pos.last_check_time) if pos.last_check_time else pd.Timestamp(pos.entry_time)
    # tz を統一
    if last_check.tz is not None:
        last_check = last_check.tz_convert("UTC").tz_localize(None)
    idx = df_short.index
    if idx.tz is not None:
        df_short = df_short.copy()
        df_short.index = idx.tz_convert("UTC").tz_localize(None)

    # last_check より後のバーのみを評価
    bars = df_short[df_short.index > last_check]
    if bars.empty:
        return None

    pip = pip_size(pos.pair)
    sp = spread_price(pos.pair)

    for ts, bar in bars.iterrows():
        sl_hit = (
            (pos.direction == "long" and bar["Low"] <= pos.stop_loss) or
            (pos.direction == "short" and bar["High"] >= pos.stop_loss)
        )
        tp_hit = (
            (pos.direction == "long" and bar["High"] >= pos.take_profit) or
            (pos.direction == "short" and bar["Low"] <= pos.take_profit)
        )
        if not (sl_hit or tp_hit):
            continue

        if sl_hit and tp_hit:
            exit_price = pos.stop_loss
            reason = "sl_tp_ambiguous"
        elif sl_hit:
            exit_price = pos.stop_loss
            reason = "sl"
        else:
            exit_price = pos.take_profit
            reason = "tp"

        # スプレッド適用 (long なら exit 下方向、short なら上方向)
        if pos.direction == "long":
            eff_exit = exit_price - sp
            pnl_price = eff_exit - pos.entry_price
            risk = pos.entry_price - pos.stop_loss
        else:
            eff_exit = exit_price + sp
            pnl_price = pos.entry_price - eff_exit
            risk = pos.stop_loss - pos.entry_price

        return PaperTrade(
            id=pos.id,
            pair=pos.pair,
            method=pos.method,
            direction=pos.direction,
            entry_type=pos.entry_type,
            entry_time=pos.entry_time,
            entry_price=pos.entry_price,
            stop_loss=pos.stop_loss,
            take_profit=pos.take_profit,
            score=pos.score,
            exit_time=ts.isoformat(),
            exit_price=eff_exit,
            exit_reason=reason,
            pnl_pips=pnl_price / pip,
            pnl_r=pnl_price / risk if risk else 0.0,
        )

    # 未到達 → last_check_time を更新するだけ
    pos.last_check_time = bars.index[-1].isoformat()
    return None
