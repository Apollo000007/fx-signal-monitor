# FX Signal Monitor — スマホ / Web からアクセスできる無料デプロイガイド

バックエンドサーバーを 24 時間立てずに、GitHub Actions + Vercel だけで
常時動作する無料デプロイの手順です。LINE / WhatsApp / Telegram / Discord
への新規アラート通知もすべて無料で動きます。

---

## アーキテクチャ

```
┌─────────────────────┐   15分ごとに cron
│  GitHub Actions     │──────────────┐
│  (scripts/build_    │              │ yfinance から取得・分析
│   static.py)        │              │ signals.json を生成
└─────────┬───────────┘              │ LINE/WhatsApp 通知送信
          │ git push                 ▼
          │                 frontend/public/api/*.json
          ▼
┌─────────────────────┐
│  GitHub repo (main) │
└─────────┬───────────┘
          │ 自動デプロイ
          ▼
┌─────────────────────┐       HTTPS
│  Vercel (無料)      │◀──────────── スマホ / PC ブラウザ
└─────────────────────┘
```

- **GitHub Actions**: 15 分ごとに `build_static.py` を実行 → 分析結果 JSON を生成 → 新アラートを通知 → repo に commit
- **Vercel**: repo の push を検知して Next.js を自動デプロイ
- **バックエンドサーバー不要**: スリープ・コールドスタート・課金リスクなし

**制限事項**:
- 更新間隔は **最短 15 分** (GitHub Actions cron の制約)
- GitHub Actions 無料枠: public repo なら **完全無制限**。private repo でも月 2000 分無料 (このワークフローは 1 回 30 秒程度 = 月 1000 分程度)

---

## 手順

### ① リポジトリを GitHub に push

```bash
cd C:\Users\hayab\Desktop\Bank
git init
git add .
git commit -m "initial commit"
# GitHub で新規 repo 作成後:
git remote add origin https://github.com/<your_account>/fx-signal-monitor.git
git branch -M main
git push -u origin main
```

**public repo にすると GitHub Actions 完全無料、Vercel も無料。**

### ② 通知設定 (LINE / WhatsApp など、使うチャネルだけで OK)

GitHub repo の **Settings → Secrets and variables → Actions → New repository secret** に以下を登録します。

#### LINE (月 200 通まで無料)

1. <https://developers.line.biz/console/> にアクセス
2. プロバイダー作成 → 「Messaging API」チャネルを作成
3. **チャネルアクセストークン (長期)** を発行 → `LINE_TOKEN` として Secret に登録
4. 作成した Bot を友だち追加
5. 自分の **User ID** を確認 (チャネル基本設定ページ下部) → `LINE_USER_ID` として登録

#### WhatsApp (CallMeBot、完全無料)

1. スマホの WhatsApp で **+34 644 77 29 80** を連絡先に追加
2. その連絡先に `I allow callmebot to send me messages to this number` と送信
3. 数分後に API key が返ってきたら:
   - `WHATSAPP_PHONE`: 自分の電話番号 (国番号込み、+ 抜き)。日本の 090-1234-5678 なら `819012345678`
   - `WHATSAPP_APIKEY`: 受信した API key
4. 参考: <https://www.callmebot.com/blog/free-api-whatsapp-messages/>

#### Telegram (完全無料・無制限、おまけ)

1. Telegram で `@BotFather` を検索 → `/newbot` → 指示通り Bot 作成
2. 受け取った Bot Token を `TELEGRAM_BOT_TOKEN` として登録
3. 作成した Bot にトーク画面で何か送信
4. ブラウザで `https://api.telegram.org/bot<TOKEN>/getUpdates` を開いて `chat.id` を確認 → `TELEGRAM_CHAT_ID` として登録

#### Discord (予備)

1. Discord サーバー → チャンネル設定 → 連携サービス → ウェブフック → 新規作成
2. URL を `DISCORD_WEBHOOK_URL` として登録

### ③ Workflow を初回実行

GitHub repo → **Actions タブ → Refresh FX Signals → Run workflow** で手動実行。
初回は `frontend/public/api/signals.json` などが生成されます。

以降は 15 分ごとに自動実行されます。

### ④ Vercel にフロントエンドをデプロイ

1. <https://vercel.com> にサインアップ (GitHub アカウントでログイン可)
2. **Add New… → Project** → さっきの GitHub repo を import
3. **Root Directory** を `frontend` に設定
4. **Environment Variables** に:
   - `NEXT_PUBLIC_STATIC_MODE` = `true`
5. **Deploy** ボタン

数分でデプロイ完了 → `https://<project>.vercel.app` のような URL が発行されます。
スマホのブラウザでもそのままアクセス可能です。

### ⑤ データ更新頻度

#### デフォルト構成 (このまま使える)

- GitHub Actions cron が **5 分間隔** で `scripts/build_static.py` を走らせ、
  yfinance から最新値を取得し `frontend/public/api/*.json` に書き出して push
- Vercel が push を検知して自動再デプロイ (CDN 反映に数十秒〜1 分)
- ブラウザは 30 秒ごとに `signals.json` を fetch
- **結果: 約 5〜6 分の更新サイクル** (GitHub Actions のジッタにより 5〜15 分の幅あり)

cron 設定: [`.github/workflows/refresh-signals.yml`](.github/workflows/refresh-signals.yml)
```yaml
on:
  schedule:
    - cron: "*/5 * * * *"   # 5 分間隔。GitHub Actions の最短値。
```

#### リアルタイム化したい場合 (任意・OANDA Practice)

**OANDA グローバル版 (`oanda.com`、`.jp` ではない)** に登録すれば、ブラウザが 3 秒間隔で
ティックを取得できます。日本居住者は Practice (Demo) なら通常登録可能。

##### セットアップ
1. <https://www.oanda.com/sign-up/> で **Demo (Practice)** を選択
   - 日本居住者で `.jp` にリダイレクトされる場合は VPN で米国/英国経由で登録 (Practice は実取引なしのため法的にも問題なし)
2. ログイン → **Manage API Access** → **Generate** で Personal Access Token を発行
3. 同ページ上部の **Account ID** (例: `101-001-12345678-001`) をコピー
4. Vercel Project → **Settings → Environment Variables** に追加:

| Key | Value | Environments |
|---|---|---|
| `OANDA_API_TOKEN` | 発行した Token | Production, Preview |
| `OANDA_ACCOUNT_ID` | Account ID | Production, Preview |
| `OANDA_ENV` | `practice` (本番口座なら `live`) | Production, Preview |

5. **Deployments → 最新 deploy → ⋯ → Redeploy** で反映

`NEXT_PUBLIC_` を **付けない** こと (サーバ側のみ参照、ブラウザバンドルに含まれない)。

##### 動作確認 (OANDA 設定後)
- フィルタバーの上に「**LIVE · OANDA tick · 15 ペア · 3 秒間隔**」と緑のインジケータ
- 各通貨カードの現在値が **「LIVE · OANDA」** 表示になり、3 秒ごとに緑/赤フラッシュ
- 通貨をクリック → サイドバーに「ライブ価格 (OANDA tick)」セクション + 各レベルへの距離 (pips)
- 価格がレベルを跨ぐと **ブラウザ通知 + ビープ音**

##### 過去に検討して採用しなかったプロバイダ
- **Finnhub**: 無料枠は forex の `/quote` が HTTP 403 を返すため不可 (実本番テスト済)
- **Yahoo Finance 直叩き**: Vercel datacenter IP がレート制限される
- **Twelve Data Free**: 800 credits/day = 30 分に 1 回しか回せない
- **Frankfurter / ExchangeRate-API**: ECB ベースの日次更新で、リアルタイムではない

→ 真のリアルタイムは認証付きブローカー API (OANDA, Saxo Demo 等) しか実用解がない。

#### よくある質問
- **5 分間隔より遅い?**: GitHub Actions cron は混雑時に 5〜15 分のジッタが出ます。`*/5` 指定は「最短目標」値
- **OANDA Practice の API トークンに期限は?**: 60 日無操作で失効。チャートを定期的に見れば自動延長
- **OANDA グローバル登録できない**: 日本 IP からはオプトインされるリダイレクトでもブラウザの言語/国設定を US 英語にすると通る場合あり。それでも無理なら VPN 経由で登録 → 利用は日本 IP で OK
- **iOS Safari でも通知?**: ホーム画面に追加した PWA のみ対応。音 (ビープ) は鳴ります
- **更新頻度を変えたい**: `frontend/src/app/page.tsx` の `useLivePrices(liveSymbols, { intervalMs: 60_000 })` を変更

---

### ⑥ (任意) 独自ドメイン

Vercel Project → Settings → Domains → ドメインを追加すれば独自ドメイン化も可能 (ドメイン自体は別途取得)。

---

## 動作の流れ

1. `*/15 * * * *` (UTC) に GitHub Actions の cron が発火
2. `scripts/build_static.py` が:
   - `_compute_signals()` を呼んで全ペア分析
   - `frontend/public/api/signals.json`, `config.json`, `chart/*.json` を書き出し
   - `state/seen_alerts.json` と照合して **新規アラート** だけ抽出
   - 新アラートを LINE / WhatsApp / Telegram / Discord に送信
3. git commit → git push
4. Vercel が push を検知して再デプロイ (約 30 秒)
5. ユーザーのブラウザは 30 秒ごとに `/api/signals.json` を fetch している
   (`?t=<timestamp>` でキャッシュバスター付き) ので 1 分以内には新データが反映

---

## トラブルシュート

**Q. 「スコアのバーが動かない」**
→ `public/api/signals.json` の timestamp を確認。古ければ Workflow が失敗している可能性あり。Actions タブでログを確認。

**Q. 「LINE が来ない」**
→ 月 200 通を超えた可能性 (LINE Messaging API の制限)。WhatsApp か Telegram にフォールバック。

**Q. 「WhatsApp が来ない」**
→ CallMeBot の API key は取得後 7 日以内に 1 通目を送らないと失効することがあります。再アクティベートしてください。

**Q. 「データが 15 分より早く欲しい」**
→ GitHub Actions の `cron` 精度は環境都合で 5〜20 分揺れます。短いサイクルが必要なら Oracle Cloud Always Free VM (4 OCPU / 24GB RAM、完全無料、24時間稼働) でバックエンドを立てる方法がありますが、設定は複雑です。

**Q. ローカル開発は?**
→ `.env.local` に `NEXT_PUBLIC_STATIC_MODE=false` と書けば従来通り FastAPI バックエンドをプロキシ経由で叩きます。`start.bat` もそのまま動きます。

---

## コスト試算

| 項目 | 料金 |
|---|---|
| GitHub repo (public) | 無料 |
| GitHub Actions (public repo) | 無料・無制限 |
| Vercel Hobby | 無料 (帯域 100GB/月、個人用途なら十分) |
| LINE Messaging API | 無料 (月 200 通) |
| WhatsApp (CallMeBot) | 無料 |
| Telegram Bot | 無料・無制限 |
| Discord Webhook | 無料・無制限 |
| **合計** | **0 円 / 月** |
