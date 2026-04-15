"""設定ファイル。監視する銘柄、アラート閾値、通知先を変更する場合はここを編集。"""

# 監視する通貨ペア {表示名: yfinanceシンボル}
PAIRS = {
    # Majors
    "USD/JPY": "USDJPY=X",
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "AUD/USD": "AUDUSD=X",
    "NZD/USD": "NZDUSD=X",
    "USD/CAD": "USDCAD=X",
    "USD/CHF": "USDCHF=X",
    # JPY crosses
    "EUR/JPY": "EURJPY=X",
    "GBP/JPY": "GBPJPY=X",
    "AUD/JPY": "AUDJPY=X",
    "NZD/JPY": "NZDJPY=X",
    "CAD/JPY": "CADJPY=X",
    "CHF/JPY": "CHFJPY=X",
    "ZAR/JPY": "ZARJPY=X",
    # EUR cross
    "EUR/GBP": "EURGBP=X",
}

# このスコア以上でアラート発火（満点100）
ALERT_THRESHOLD = 75

# 自動更新間隔（秒）
REFRESH_SECONDS = 300

# --- 通知設定 ---

# 音アラート（Windows winsound.Beep）
PLAY_SOUND = True

# Discord Webhook URL（Noneで無効）
# Discordサーバー → チャンネル設定 → 連携サービス → ウェブフック から取得
DISCORD_WEBHOOK_URL = None

# LINE Messaging API 設定（Noneで無効）
# 注: LINE Notify サービスは 2025/3 で終了したため、
# LINE Developers で Messaging API チャンネルを作成して Bot を追加する方式。
# 無料枠: 月 200 通 push
# https://developers.line.biz/
LINE_CHANNEL_ACCESS_TOKEN = None
LINE_USER_ID = None

# WhatsApp (CallMeBot) 設定（Noneで無効）
# 完全無料・Meta 登録不要。個人用途に最適。
# 事前: WhatsApp で +34 644 77 29 80 に
#   "I allow callmebot to send me messages" を送信 → API key 返送
# 電話番号は国番号込みで "+" なし。例: 日本の 090-1234-5678 → "819012345678"
# https://www.callmebot.com/blog/free-api-whatsapp-messages/
WHATSAPP_PHONE = None
WHATSAPP_APIKEY = None

# Telegram Bot API 設定（Noneで無効）
# 完全無料・無制限。@BotFather で Bot 作成。
TELEGRAM_BOT_TOKEN = None
TELEGRAM_CHAT_ID = None

# --- タイムフレーム設定 ---
# 3時間軸構成: 長期=日足（大方針）/ 中期=4H（主軸・トレンド判定）/ 短期=15M（エントリートリガー）
# yfinance は 4h ネイティブ非対応のため、1h データを 4h にリサンプリングする。

# 長期足: 大まかな方向性
LONG_INTERVAL = "1d"
LONG_PERIOD = "2y"
LONG_RESAMPLE = None
LONG_LABEL = "日足"

# 中期足 (メイン): 4H にリサンプル
MID_INTERVAL = "1h"
MID_PERIOD = "730d"     # 1h の最大期間 (~2年)
MID_RESAMPLE = "4h"     # ← 4時間足に集約
MID_LABEL = "4H"

# 短期足: エントリートリガー専用
SHORT_INTERVAL = "15m"
SHORT_PERIOD = "60d"
SHORT_RESAMPLE = None
SHORT_LABEL = "15M"
