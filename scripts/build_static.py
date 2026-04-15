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


def _format_alert(pair: str, method: str, sub: dict) -> str:
    arrow = "↑ LONG" if sub["direction"] == "long" else "↓ SHORT"
    lines = [
        f"[FX] {pair} {arrow}  ({method.upper()})",
        f"スコア: {sub['score']}/100",
    ]
    if sub.get("price") is not None:
        lines.append(f"Entry: {sub['price']:.4f}")
    if sub.get("stop_loss") is not None:
        lines.append(f"SL   : {sub['stop_loss']:.4f}")
    if sub.get("take_profit") is not None:
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


# ---------- メイン ------------------------------------------------------------

METHODS_TO_NOTIFY = ("triple", "both", "claude", "pdhl", "orz")


def detect_new_alerts(records: list[dict], seen: dict[str, float], now_ts: float):
    """seen を更新しつつ、今回新規となったアラートのリストを返す。

    同一 (pair, method, direction) は REBROADCAST_SEC 以内なら再送しない。
    method 優先度: triple > both > claude > pdhl > orz
    同一ペアに対しては最上位の method だけ通知 (ノイズ抑制)。
    """
    new_alerts: list[tuple[str, str, dict]] = []
    for rec in records:
        pair = rec["pair"]
        for method in METHODS_TO_NOTIFY:
            sub = rec.get(method)
            if not sub or not sub.get("is_alert"):
                continue
            if sub["direction"] == "none":
                continue
            key = f"{pair}:{method}:{sub['direction']}"
            prev = seen.get(key, 0.0)
            if (now_ts - prev) < REBROADCAST_SEC:
                continue
            seen[key] = now_ts
            new_alerts.append((pair, method, sub))
            break  # このペアは最上位メソッドだけ
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

    return 0


if __name__ == "__main__":
    sys.exit(main())
