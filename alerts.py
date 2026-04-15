"""通知モジュール: 音(Windows)、Discord Webhook、LINE Messaging API。"""
from __future__ import annotations

import requests

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False


def play_beep() -> None:
    """アラート音を鳴らす。Windows以外では何もしない。"""
    if not HAS_WINSOUND:
        return
    try:
        winsound.Beep(1200, 250)
        winsound.Beep(1600, 250)
        winsound.Beep(1200, 250)
    except RuntimeError:
        pass


def send_discord(webhook_url: str, content: str) -> bool:
    """Discord Webhook へメッセージ送信。"""
    try:
        r = requests.post(webhook_url, json={"content": content[:1900]}, timeout=10)
        return r.status_code in (200, 204)
    except Exception as e:
        print(f"[alerts] discord send error: {e}")
        return False


def send_line_push(access_token: str, user_id: str, text: str) -> bool:
    """LINE Messaging API でプッシュメッセージ送信。要Bot設定。"""
    try:
        r = requests.post(
            "https://api.line.me/v2/bot/message/push",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
            },
            json={"to": user_id, "messages": [{"type": "text", "text": text[:4900]}]},
            timeout=10,
        )
        return r.status_code == 200
    except Exception as e:
        print(f"[alerts] line send error: {e}")
        return False


def send_whatsapp_callmebot(phone: str, apikey: str, text: str) -> bool:
    """CallMeBot WhatsApp API にメッセージ送信。完全無料 (個人用途)。

    事前準備:
      1. WhatsApp で +34 644 77 29 80 に "I allow callmebot to send me messages"
         を送信する
      2. 返信で API key が届く
      3. config.py に WHATSAPP_PHONE (国番号付き、+81-... は 81... にする) と
         WHATSAPP_APIKEY を設定

    参考: https://www.callmebot.com/blog/free-api-whatsapp-messages/
    """
    try:
        r = requests.get(
            "https://api.callmebot.com/whatsapp.php",
            params={
                "phone": phone,
                "text": text[:1500],
                "apikey": apikey,
            },
            timeout=15,
        )
        return 200 <= r.status_code < 300
    except Exception as e:
        print(f"[alerts] whatsapp send error: {e}")
        return False


def send_telegram(bot_token: str, chat_id: str, text: str) -> bool:
    """Telegram Bot API にメッセージ送信。完全無料・無制限。

    事前準備:
      1. Telegram で @BotFather にトーク → /newbot → 指示通りに作成
      2. bot_token を取得
      3. 作成した Bot にトーク送信後、
         https://api.telegram.org/bot<token>/getUpdates を開いて
         自分の chat_id を確認
    """
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": text[:3900]},
            timeout=10,
        )
        return r.status_code == 200
    except Exception as e:
        print(f"[alerts] telegram send error: {e}")
        return False


def format_signal_message(signal) -> str:
    tag = "[LONG]" if signal.direction == "long" else "[SHORT]" if signal.direction == "short" else "[--]"
    lines = [
        f"FXシグナル {tag} {signal.pair}  スコア: {signal.score}/100",
        f"価格: {signal.price:.4f}",
    ]
    if signal.stop_loss:
        lines.append(f"損切目安: {signal.stop_loss:.4f}")
    if signal.take_profit:
        lines.append(f"利確目標: {signal.take_profit:.4f}")
    lines.append("根拠:")
    for r in signal.reasons:
        lines.append(f"  ・{r}")
    if signal.warnings:
        lines.append("警告:")
        for w in signal.warnings:
            lines.append(f"  ! {w}")
    return "\n".join(lines)
