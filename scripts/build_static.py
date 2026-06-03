"""GitHub Actions (cron) から呼ばれるスタティックビルドスクリプト。

実行内容:
  1. 既存の _compute_signals() でシグナル計算
  2. frontend/public/api/signals.json  (フロント用 signals 全件)
  3. frontend/public/api/config.json   (alert_threshold 等)
  4. frontend/public/api/chart/{symbol_sanitized}_{tf}.json × 監視ペア × 3TF
  5. 新規アラート検出 (state/seen_alerts.json と diff)
  6. LINE / WhatsApp / Telegram / Discord 通知 (env var / config 値が有れば)

環境変数で config をオーバーライドできる (GitHub Secrets 想定):
  LINE_TOKEN, LINE_USER_ID
  WHATSAPP_PHONE, WHATSAPP_APIKEY
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
  DISCORD_WEBHOOK_URL
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

# --- repo root をパスに追加 (scripts/ から実行されても api.py が import できるように)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
import alerts  # noqa: E402
import risk  # noqa: E402
from api import (  # noqa: E402
    _compute_signals,
    _cache,
    _df_to_candles,
    _series_to_line,
)
from indicators import ichimoku, sma  # noqa: E402

OUT_DIR = ROOT / "frontend" / "public" / "api"
CHART_DIR = OUT_DIR / "chart"
STATE_DIR = ROOT / "state"
STATE_FILE = STATE_DIR / "seen_alerts.json"
CALENDAR_FILE = OUT_DIR / "calendar.json"
CALENDAR_CACHE = STATE_DIR / "calendar_cache.json"


# ---------- 通知 --------------------------------------------------------------

def _env(name: str, fallback):
    v = os.environ.get(name)
    return v if v else fallback


def send_notifications(message: str) -> None:
    """全チャネルに送信を試みる。設定が無いチャネルはスキップ。"""
    # LINE
    line_token = _env("LINE_TOKEN", getattr(config, "LINE_CHANNEL_ACCESS_TOKEN", None))
    line_user = _env("LINE_USER_ID", getattr(config, "LINE_USER_ID", None))
    if line_token and line_user:
        ok = alerts.send_line_push(line_token, line_user, message)
        print(f"[notify] LINE: {'ok' if ok else 'FAILED'}")

    # WhatsApp (CallMeBot)
    wa_phone = _env("WHATSAPP_PHONE", getattr(config, "WHATSAPP_PHONE", None))
    wa_key = _env("WHATSAPP_APIKEY", getattr(config, "WHATSAPP_APIKEY", None))
    if wa_phone and wa_key:
        ok = alerts.send_whatsapp_callmebot(wa_phone, wa_key, message)
        print(f"[notify] WhatsApp: {'ok' if ok else 'FAILED'}")

    # Telegram
    tg_token = _env("TELEGRAM_BOT_TOKEN", getattr(config, "TELEGRAM_BOT_TOKEN", None))
    tg_chat = _env("TELEGRAM_CHAT_ID", getattr(config, "TELEGRAM_CHAT_ID", None))
    if tg_token and tg_chat:
        ok = alerts.send_telegram(tg_token, tg_chat, message)
        print(f"[notify] Telegram: {'ok' if ok else 'FAILED'}")

    # Discord
    dc_url = _env("DISCORD_WEBHOOK_URL", getattr(config, "DISCORD_WEBHOOK_URL", None))
    if dc_url:
        ok = alerts.send_discord(dc_url, message)
        print(f"[notify] Discord: {'ok' if ok else 'FAILED'}")


def _mm_levels(sub: dict):
    """資産管理ベースの利確レベルを算出 (通知整形用、risk.py を流用)。

    sub["take_profit"] は api 側で既に最低2R床が適用済み (= primary)。
    ここでは推奨3R と実効RR を併記するために再計算する。
    """
    entry = sub.get("price")
    sl = sub.get("stop_loss")
    direction = sub.get("direction")
    if entry is None or sl is None or direction not in ("long", "short"):
        return None
    r = abs(entry - sl)
    if r <= 0:
        return None
    primary = sub.get("take_profit")  # api で 2R 床適用済み
    if primary is None:
        primary = risk.min_rr_tp(entry, sl, None, direction)
    tp3 = risk.rr_target(entry, sl, direction, risk.RECOMMENDED_RR)
    rr = risk.r_multiple(entry, sl, primary, direction) or risk.DEFAULT_MIN_RR
    return {"tp3": tp3, "primary": primary, "rr": rr}


def _format_alert(pair: str, method: str, sub: dict) -> str:
    arrow = "↑ LONG" if sub["direction"] == "long" else "↓ SHORT"
    lines = [
        f"[FX] {pair} {arrow}  ({method.upper()})",
        f"スコア: {sub['score']}/100",
    ]
    if sub.get("pattern_name"):
        rk = sub.get("rank")
        lines.append(f"パターン: {sub['pattern_name']}" + (f" 【{rk}】" if rk else ""))
    if sub.get("price") is not None:
        lines.append(f"Entry: {sub['price']:.4f}")
    if sub.get("stop_loss") is not None:
        lines.append(f"SL (1R)    : {sub['stop_loss']:.4f}")
    mm = _mm_levels(sub)
    if mm is not None:
        lines.append(f"利確 最低2R : {mm['primary']:.4f}  (RR {mm['rr']:.2f})")
        if mm.get("tp3") is not None:
            lines.append(f"利確 推奨3R : {mm['tp3']:.4f}")
        lines.append("※ SL=1R。1Rで半分利確→建値移動→残りを3Rへ(損小利大)")
    elif sub.get("take_profit") is not None:
        lines.append(f"TP   : {sub['take_profit']:.4f}")
    if sub.get("reasons"):
        lines.append("根拠:")
        for r in sub["reasons"][:4]:
            lines.append(f"  ・{r}")
    return "\n".join(lines)


# ---------- state (送信済みアラート履歴) --------------------------------------

def load_seen() -> dict[str, float]:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_seen(seen: dict[str, float]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(seen, ensure_ascii=False, indent=2), encoding="utf-8")


# 同一アラートは最短 3 時間は再送しない (方向転換等で is_alert が明滅するのを抑制)
REBROADCAST_SEC = 3 * 3600


# ---------- 書き出し ----------------------------------------------------------

def _sanitize_symbol(symbol: str) -> str:
    return symbol.replace("=", "_").replace("/", "_").replace("\\", "_")


def write_signals(records: list[dict], now: datetime) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "signals": records,
        "updated_at": now.isoformat(),
        "cached": False,
    }
    (OUT_DIR / "signals.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def write_config() -> None:
    payload = {
        "alert_threshold": config.ALERT_THRESHOLD,
        "refresh_seconds": config.REFRESH_SECONDS,
        "long_label": config.LONG_LABEL,
        "mid_label": config.MID_LABEL,
        "short_label": config.SHORT_LABEL,
        "pair_count": len(config.PAIRS),
    }
    (OUT_DIR / "config.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def write_charts() -> None:
    """_compute_signals() が埋めた _cache["tf_data"] から各ペア × 3TF を書き出す。"""
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    for (symbol, tf), (df, _at) in _cache["tf_data"].items():
        if df is None or df.empty:
            continue
        try:
            s20 = sma(df["Close"], 20)
            s50 = sma(df["Close"], 50)
            s100 = sma(df["Close"], 100)
            _, _, senkou_a, senkou_b = ichimoku(df["High"], df["Low"])
            payload = {
                "symbol": symbol,
                "tf": tf,
                "candles": _df_to_candles(df),
                "sma20": _series_to_line(df, s20),
                "sma50": _series_to_line(df, s50),
                "sma100": _series_to_line(df, s100),
                "senkou_a": _series_to_line(df, senkou_a),
                "senkou_b": _series_to_line(df, senkou_b),
            }
            fname = f"{_sanitize_symbol(symbol)}_{tf}.json"
            (CHART_DIR / fname).write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
        except Exception as e:
            print(f"[chart] {symbol}/{tf} 書き出し失敗: {e}")


def write_calendar(now: datetime) -> None:
    """FX 経済カレンダー + 当日リスクスコアを calendar.json に書き出す。

    フェッチ失敗時は前回キャッシュ (state/calendar_cache.json) にフォールバック
    し、UI が空にならないようにする。signals 本体とは独立 (失敗しても続行)。
    """
    from news_calendar import build_calendar_payload

    payload = build_calendar_payload(now)
    if payload.get("ok"):
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        CALENDAR_CACHE.write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
    else:
        # 取得失敗 → 直近キャッシュがあれば updated_at だけ差し替えて使う
        try:
            cached = json.loads(CALENDAR_CACHE.read_text(encoding="utf-8"))
            cached["updated_at"] = now.isoformat()
            cached["risk"]["summary"] = (
                cached["risk"].get("summary", "")
                + "（最新取得失敗・前回データ表示中）"
            )
            payload = cached
            print("[calendar] feed failed → using cached payload")
        except Exception:
            print("[calendar] feed failed and no cache → minimal payload")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CALENDAR_FILE.write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    r = payload.get("risk", {})
    print(f"[calendar] {len(payload.get('events', []))} events, "
          f"risk={r.get('stars')}★ {r.get('level')}")


# ---------- メイン ------------------------------------------------------------

# +EV 集中: 通知は実証手法のみ (PDHL=1:1 / ORZ=不安定TP は UI 参考表示に降格)
METHODS_TO_NOTIFY = ("triple", "dtp", "pa")

# 相関・同時数キャップ (2週間デモの GBP/USD 3連敗・JPY系多重を防ぐ)
MAX_ALERTS_PER_CYCLE = 4    # 1 サイクルで送る新規通知の上限
MAX_PER_CURRENCY = 1        # 同一通貨を含むペアは 1 サイクル最大 N 件


def _currencies(pair: str) -> tuple[str, ...]:
    return tuple(c.strip().upper() for c in pair.split("/") if c.strip())


def detect_new_alerts(records: list[dict], seen: dict[str, float], now_ts: float):
    """seen を更新しつつ、今回新規となったアラートのリストを返す。

    同一 (pair, method, direction) は REBROADCAST_SEC 以内なら再送しない。
    method 優先度: triple > dtp > pa。同一ペアは最上位 method だけ通知。
    さらに相関抑制: 1 サイクル合計 MAX_ALERTS_PER_CYCLE 件、同一通貨は
    MAX_PER_CURRENCY 件までに制限 (JPY系/USD系の重ね打ちを防止)。
    優先度の高い手法 (triple>dtp>pa) を先に確保するため、候補を収集後に並べ替える。
    """
    # --- 候補収集 (ペアごとに最上位 method 1 件、クールダウン通過分) ---
    candidates: list[tuple[str, str, dict, int]] = []  # (pair, method, sub, prio)
    for rec in records:
        pair = rec["pair"]
        for prio, method in enumerate(METHODS_TO_NOTIFY):
            sub = rec.get(method)
            if not sub or not sub.get("is_alert"):
                continue
            if sub["direction"] == "none":
                continue
            key = f"{pair}:{method}:{sub['direction']}"
            if (now_ts - seen.get(key, 0.0)) < REBROADCAST_SEC:
                continue
            candidates.append((pair, method, sub, prio))
            break  # このペアは最上位メソッドだけ

    # --- 優先度順 (手法優先 → スコア降順) に確定。相関/同時数キャップを適用 ---
    candidates.sort(key=lambda c: (c[3], -int(c[2].get("score", 0))))
    new_alerts: list[tuple[str, str, dict]] = []
    ccy_count: dict[str, int] = {}
    for pair, method, sub, _prio in candidates:
        if len(new_alerts) >= MAX_ALERTS_PER_CYCLE:
            break
        ccys = _currencies(pair)
        if any(ccy_count.get(c, 0) >= MAX_PER_CURRENCY for c in ccys):
            continue  # 同一通貨の重ね打ちを抑制
        for c in ccys:
            ccy_count[c] = ccy_count.get(c, 0) + 1
        seen[f"{pair}:{method}:{sub['direction']}"] = now_ts
        new_alerts.append((pair, method, sub))
    return new_alerts


def main() -> int:
    print(f"[build_static] start at {datetime.now(timezone.utc).isoformat()}")
    try:
        records = _compute_signals()
    except Exception:
        traceback.print_exc()
        return 1

    now = datetime.now(timezone.utc)
    now_ts = now.timestamp()

    write_signals(records, now)
    write_config()
    write_charts()
    print(f"[build_static] wrote {len(records)} signals + charts")

    # 経済カレンダー + 当日リスクスコア (失敗しても signals は出す)
    try:
        write_calendar(now)
    except Exception as e:
        traceback.print_exc()
        print(f"[build_static] calendar error (continuing): {e}")

    # 新規アラート検出 → 通知
    seen = load_seen()
    # 古いキーを掃除 (7 日経過したエントリを削除)
    seen = {k: v for k, v in seen.items() if now_ts - v < 7 * 24 * 3600}
    new_alerts = detect_new_alerts(records, seen, now_ts)
    save_seen(seen)

    print(f"[build_static] {len(new_alerts)} new alerts")
    for pair, method, sub in new_alerts:
        msg = _format_alert(pair, method, sub)
        print("---")
        print(msg)
        send_notifications(msg)

    # --- Paper Trade (Phase B): 仮想ポジションの open/close + UI 用統計出力 ---
    try:
        from paper_trade.runner import tick as paper_tick
        paper_tick(records, now, send_telegram=send_notifications)
        print("[build_static] paper trade tick done")
    except Exception as e:
        traceback.print_exc()
        print(f"[build_static] paper trade error (continuing): {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
