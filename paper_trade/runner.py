"""cron から呼ばれる Paper Trade ランナー。

scripts/build_static.py の `main()` の末尾で
    from paper_trade.runner import tick
    tick(records, now)
として呼び出す。

処理:
  1. state/paper_positions.json を読み込み
  2. 各 open position について最新 15M データで SL/TP 到達判定 → 到達なら close
  3. records から is_alert=True のシグナルを取り出し、同 pair に open が無ければ new open
  4. state/paper_positions.json / state/paper_history.json を更新
  5. frontend/public/api/paper.json に集計値を出力 (UI で表示)
  6. (任意) 日付が変わったら前日サマリを Telegram に送る

設計判断:
  - is_alert を出した手法 5 つすべてで個別にポジションを建てる (検証目的)
  - 1 ペア × 1 手法に対して同時に 1 ポジションのみ (重ね打ち禁止)
  - SL/TP 到達判定は 15M バーの High/Low (バックテストと同じルール)
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "state"
POSITIONS_FILE = STATE_DIR / "paper_positions.json"
HISTORY_FILE = STATE_DIR / "paper_history.json"
LAST_SUMMARY_FILE = STATE_DIR / "paper_last_summary.json"
OUT_FILE = ROOT / "frontend" / "public" / "api" / "paper.json"

# 全 5 手法を Paper Trade 対象 (検証用)
METHODS = ("orz", "pdhl", "triple", "dtp", "pa", "mtf")

# 同一 pair × method に対する同時 open は 1 件のみ
# 同一 pair に複数手法のポジションは並行 OK


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _fetch_short_data_for_pairs(pairs_with_symbols: list[tuple[str, str]]) -> dict:
    """open position のあるペアだけ 15M データを取得して {symbol: df} を返す。"""
    if not pairs_with_symbols:
        return {}
    try:
        from data_fetcher import fetch_multi
        symbols = [s for _, s in pairs_with_symbols]
        # 直近 1 日分あれば SL/TP 判定には十分
        return fetch_multi(symbols, interval="15m", period="5d", resample=None) or {}
    except Exception as e:
        print(f"[paper_trade] fetch_multi error: {e}")
        return {}


def _strip_tz(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    if df.index.tz is not None:
        return df.tz_convert("UTC").tz_localize(None)
    return df


def tick(records: list[dict], now: datetime, send_telegram=None):
    """cron 1 サイクル分の Paper Trade 処理。

    records: api._compute_signals() が返す list[dict] と同形式
             各 dict には orz/pdhl/both/claude/triple の sub method dict が入っている
    now    : 現在時刻 (UTC, tz-aware)
    send_telegram: callable (message: str) -> None  Telegram 通知関数 (任意)
    """
    from .broker import (
        PaperPosition, PaperTrade,
        load_positions, save_positions,
        append_history, load_history,
        open_position, check_exit,
    )

    positions = load_positions(POSITIONS_FILE)
    closed_this_tick: list[PaperTrade] = []
    opened_this_tick: list[PaperPosition] = []

    # ----- 1. open position の SL/TP 判定 -----
    if positions:
        pair_symbols_for_check = list({(p.pair, _find_symbol(records, p.pair)) for p in positions})
        pair_symbols_for_check = [(p, s) for p, s in pair_symbols_for_check if s]
        short_data = _fetch_short_data_for_pairs(pair_symbols_for_check)
        # tz 統一
        for k in list(short_data.keys()):
            short_data[k] = _strip_tz(short_data[k])

        new_positions = []
        for pos in positions:
            sym = _find_symbol(records, pos.pair)
            df = short_data.get(sym) if sym else None
            closed = check_exit(pos, df) if df is not None else None
            if closed:
                append_history(HISTORY_FILE, closed)
                closed_this_tick.append(closed)
                print(f"[paper_trade] CLOSE {pos.pair} {pos.method} {pos.direction} → {closed.exit_reason} "
                      f"({closed.pnl_r:+.2f}R / {closed.pnl_pips:+.1f}pips)")
            else:
                new_positions.append(pos)
        positions = new_positions

    # ----- 2. 新規 alert を open -----
    now_ts = pd.Timestamp(now).tz_convert("UTC").tz_localize(None)
    for rec in records:
        pair = rec.get("pair")
        symbol = rec.get("symbol")
        if not pair:
            continue
        for method in METHODS:
            sub = rec.get(method)
            if not sub or not sub.get("is_alert"):
                continue
            if sub.get("stop_loss") is None or sub.get("take_profit") is None or sub.get("price") is None:
                continue
            # sanity check: direction と SL/TP が整合
            direction = sub.get("direction")
            entry = float(sub["price"])
            sl = float(sub["stop_loss"])
            tp = float(sub["take_profit"])
            if direction == "long" and not (sl < entry < tp):
                continue
            if direction == "short" and not (tp < entry < sl):
                continue
            # 同 pair × method に既存ポジションがあればスキップ
            if any(p.pair == pair and p.method == method for p in positions):
                continue
            pos = open_position(
                pair, method, direction, sub.get("entry_type", "—"),
                entry, sl, tp, int(sub.get("score", 0)),
                now_ts,
            )
            positions.append(pos)
            opened_this_tick.append(pos)
            print(f"[paper_trade] OPEN {pair} {method} {direction} @ {entry:.5f} "
                  f"SL={sl:.5f} TP={tp:.5f}")

    # ----- 3. positions 保存 -----
    save_positions(POSITIONS_FILE, positions)

    # ----- 4. UI 用統計を frontend/public/api/paper.json に書き出し -----
    history = load_history(HISTORY_FILE)
    stats = _compute_paper_stats(history)
    payload = {
        "updated_at": now.isoformat(),
        "open_count": len(positions),
        "open_positions": [p.to_dict() for p in positions],
        "history_count": len(history),
        "recent_trades": history[-50:],  # 直近 50 件
        "stats": stats,
    }
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # ----- 5. (任意) 日次サマリを Telegram 送信 -----
    if send_telegram and closed_this_tick:
        # トレード close が起きた tick で「直近 close したトレード」を送る
        # (毎クローズに送ると五月雨になるので、tick 単位でまとめる)
        msg = _format_close_summary(closed_this_tick)
        send_telegram(msg)

    # 日次サマリ (1 日 1 回、UTC 0:00 過ぎ)
    if send_telegram and _should_send_daily_summary(now):
        daily = _build_daily_summary(history, now)
        if daily:
            send_telegram(daily)
            _record_summary_sent(now)


def _find_symbol(records: list[dict], pair: str) -> Optional[str]:
    for r in records:
        if r.get("pair") == pair:
            return r.get("symbol")
    return None


# ============== 統計 ==============

def _compute_paper_stats(history: list[dict]) -> dict:
    """frontend で表示する集計値を計算。"""
    if not history:
        return {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "total_r": 0.0,
            "expectancy_r": 0.0,
            "profit_factor": 0.0,
            "by_method": {},
        }
    rs = [t["pnl_r"] for t in history if t.get("pnl_r") is not None]
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r < 0]
    gross_w = sum(wins)
    gross_l = -sum(losses)
    pf = gross_w / gross_l if gross_l > 0 else float("inf") if gross_w > 0 else 0.0
    by_method: dict = {}
    for m in METHODS:
        sub = [t for t in history if t.get("method") == m]
        if not sub:
            continue
        sub_rs = [t["pnl_r"] for t in sub if t.get("pnl_r") is not None]
        sub_w = sum(1 for r in sub_rs if r > 0)
        by_method[m] = {
            "trades": len(sub),
            "wins": sub_w,
            "win_rate": sub_w / len(sub) * 100 if sub else 0.0,
            "total_r": sum(sub_rs),
            "expectancy_r": sum(sub_rs) / len(sub_rs) if sub_rs else 0.0,
        }
    return {
        "trades": len(rs),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / len(rs) * 100 if rs else 0.0,
        "total_r": sum(rs),
        "expectancy_r": sum(rs) / len(rs) if rs else 0.0,
        "profit_factor": pf if pf != float("inf") else 999.0,
        "by_method": by_method,
    }


# ============== Telegram 通知整形 ==============

def _format_close_summary(closed: list) -> str:
    lines = [f"📊 Paper Trade Close ({len(closed)} 件)"]
    for t in closed:
        emoji = "✅" if t.pnl_r > 0 else "❌"
        lines.append(f"{emoji} {t.pair} {t.method.upper()} {t.direction.upper()} "
                     f"→ {t.exit_reason.upper()}  {t.pnl_r:+.2f}R ({t.pnl_pips:+.1f}p)")
    return "\n".join(lines)


def _should_send_daily_summary(now: datetime) -> bool:
    """UTC 0:00〜0:10 の間で、まだ今日の summary を送ってなければ True。"""
    if not (0 <= now.hour == 0 and 0 <= now.minute < 10):
        return False
    try:
        last = json.loads(LAST_SUMMARY_FILE.read_text(encoding="utf-8"))
        last_date = last.get("date")
        return last_date != now.date().isoformat()
    except Exception:
        return True


def _record_summary_sent(now: datetime):
    LAST_SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAST_SUMMARY_FILE.write_text(
        json.dumps({"date": now.date().isoformat()}, ensure_ascii=False),
        encoding="utf-8",
    )


def _build_daily_summary(history: list[dict], now: datetime) -> Optional[str]:
    """前日 (UTC) にクローズされたトレードのサマリ。"""
    yesterday = (now - timedelta(days=1)).date().isoformat()
    today_close = [
        t for t in history
        if t.get("exit_time", "").startswith(yesterday)
    ]
    if not today_close:
        return None
    rs = [t["pnl_r"] for t in today_close if t.get("pnl_r") is not None]
    wins = sum(1 for r in rs if r > 0)
    losses = sum(1 for r in rs if r < 0)
    total_r = sum(rs)
    best = max(today_close, key=lambda t: t.get("pnl_r", 0))
    return (
        f"📊 Daily Summary ({yesterday})\n"
        f"Trades: {len(today_close)}  Wins: {wins}  Losses: {losses}\n"
        f"Total R: {total_r:+.2f}\n"
        f"Best: {best['pair']} {best['method'].upper()} {best['pnl_r']:+.2f}R"
    )
