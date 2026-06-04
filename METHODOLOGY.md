# FX Signal Monitor — 手法・アラート構造リファレンス

> **目的**: 本書は他の AI / 開発者が本アプリの判断ロジックを再現・拡張する際に
> 参照するための仕様書である。実装ファイル名・関数名・スコア配点まで明示し、
> 推測なしで挙動を把握できるよう構造化している。

---

## 0. 概要 (TL;DR)

- **対象**: 15 通貨ペア (主要 7、JPY クロス 7、EUR/GBP) を 24h 監視
- **時間軸**: 日足 (環境) / 4H (主軸) / 1H (補助) / 15M (トリガー)。
  MTF 手法のみ追加で週足 (日足から resample) も使用
- **稼働手法**: `triple` / `dtp`(4ペア) / `pa` / **`mtf`(日足+4H 一致+15M S/Aパターン。週/1Hは参考)**。
  `pdhl`/`orz` は降格 (参考表示)。`claude`/`both` は内部のみ
- **アラート条件**: `score ≥ ALERT_THRESHOLD (=75)` **かつ** `has_trigger=True`
- **スコア**: 0–100。15M トリガー未発火なら閾値未満にキャップ
- **資金管理**: フロントで 1R = |Entry−SL| を単位とし 2R / 3R 利確を可視化
- **通知**: 音 (Win) / Discord / LINE / WhatsApp / Telegram

---

## 1. ファイル構成

| ファイル | 役割 |
|---|---|
| `config.py` | ペア定義、閾値、TF パラメータ、通知設定 |
| `data_fetcher.py` | yfinance から OHLC 取得、4H への resample |
| `indicators.py` | SMA/EMA/RSI/MACD/ATR/一目均衡表/スイング検出/クラスタリング |
| `strategy.py` | **ORZ 手法** (`analyze_pair`, `analyze_timeframe`) |
| `strategy_pdhl.py` | **PDH/PDL 手法** (`analyze_pair_pdhl`) |
| `strategy_claude.py` | **Claude Confluence 手法** (`analyze_pair_claude`) |
| `api.py` | FastAPI ラッパ、`both`/`triple` 合成、`/api/*` 公開 |
| `alerts.py` | 通知送信 (Discord/LINE/WhatsApp/Telegram/Beep) |
| `app.py` | Tkinter デスクトップ GUI (代替 UI) |
| `frontend/` | Next.js Web UI |
| `scripts/build_static.py` | GitHub Actions 用バッチ実行 (Vercel デプロイ向け) |

---

## 2. 監視対象 (`config.PAIRS`)

```
Majors      : USD/JPY, EUR/USD, GBP/USD, AUD/USD, NZD/USD, USD/CAD, USD/CHF
JPY crosses : EUR/JPY, GBP/JPY, AUD/JPY, NZD/JPY, CAD/JPY, CHF/JPY
EUR cross   : EUR/GBP
（ZAR/JPY はスプレッド広・ボラ過大のため監視対象から除外）
```
合計 **15 ペア**。シンボルは yfinance 形式 (`EURUSD=X` 等)。

---

## 3. 時間軸 (`config.*_INTERVAL`)

| 役割 | キー | 取得元 | 期間 | 用途 |
|---|---|---|---|---|
| 長期 (環境) | `lt` | 1d × 2y | 1d ネイティブ | 大方針・障害物 |
| 中期 (主軸) | `mt` | 1h × 730d → **4h resample** | 4H | 相場分類・エントリーポイント決定 |
| 補助 | `ht` | 1h × 60d | 1h ネイティブ | 主軸との整合性チェック (`_h1_alignment`) |
| 短期 (トリガー) | `st` | 15m × 60d | 15m ネイティブ | エントリー点火 (★ トリガー) |

> yfinance は 4h ネイティブ非対応 → `data_fetcher.fetch_multi` で 1h → 4h を OHLC リサンプル。

---

## 4. インジケーター (`indicators.py`)

| 関数 | 内容 |
|---|---|
| `sma(s, n)` | 単純移動平均 |
| `ema(s, n)` | 指数移動平均 |
| `slope(s, bars=5)` | 直近 bars 本の変化率 (%) — SMA 傾斜判定 |
| `macd(c, 12, 26, 9)` | MACD line / signal / histogram |
| `rsi(c, 14)` | Wilder RSI |
| `atr(h, l, c, 14)` | Wilder ATR |
| `ichimoku(h, l)` | 転換線/基準線/先行スパン A,B (26 期間先行 shift 済) |
| `find_swings(df, w=3)` | ピボットによるスイング高安検出 |
| `cluster_levels(levels, tol=0.002)` | 近接価格レベルを平均してクラスタ化 (2 タッチ以上を採用) |

---

## 5. 4 つの基本手法

### 5.1 ORZ 手法 (`strategy.analyze_pair`)

**根拠**: ORZ 流テクニカル分析。トレンド判定 + 押し目/ブレイク/レンジ逆張り。
MACD は使わず、**SMA20/50/100 + 一目雲のみ**。

#### 5.1.1 相場タイプ判定 (`_classify_regime`)
4H 終値とインジケーターから次の 4 種に分類:
- `trend_up`   : SMA20 > 50 > 100 かつ slope20 > 0.05% かつ slope50 ≥ 0
- `trend_down` : 上記の鏡写し
- `range`      : |slope20| < 0.08% かつ |slope50| < 0.05% かつ R/S が存在
- `unclear`    : 上記以外 → **見送り**

**明瞭度 (clarity, 0-100)**: 雲との位置関係 (+30/+10/0) と スイング高安の方向一貫性 (+10 ずつ)。

#### 5.1.2 エントリー分類 (4H)
1. **`pullback`** (`_detect_pullback`)
   - 終値が SMA20/50/100 のいずれかと ±0.3% 以内
   - または SMA20-50 帯内、または S/R との接触
   - **複数根拠で +5 点ボーナス**
2. **`breakout`** (`_detect_breakout`)
   - 直近 12 本の保ち合い (幅 0.3%–2.5%) を最新足が抜けた
3. **`range_reversal`** (`_detect_range_reversal`)
   - `regime == "range"` のみ
   - 終値がレンジ高安の **20% バンド** に到達

#### 5.1.3 ★ 15M トリガー (`_reversal_trigger` / `_breakout_trigger`)
| パターン (long) | 条件 |
|---|---|
| 安値切り上げ + 陽線 | last.Low > prev_min かつ Close > Open かつ Close > prev.Close |
| 下ヒゲピンバー | lower_wick > body × 1.5 かつ Close ≥ Open |
| ダブルボトム | 直近 5 本の安値同値 ±0.15% かつ Close > Open |
| ブレイクフォロースルー | Close > prev.High かつ body/range > 0.5 (breakout 用) |
short は鏡写し。

#### 5.1.4 スコア配点 (満点 100)
| 要素 | 配点 |
|---|---|
| 4H 明瞭度 | `clarity × 0.3` (最大 30) |
| 日足整合 | 同方向トレンド +15 / レンジ +7 / 不明 +3 / 逆 0 |
| エントリー成立 | pullback 単独 +20 / 複数根拠 +25 / breakout +22 |
| 日足障害物なし | +10 (近接 0.6% 以内に SMA50/100/雲なし) |
| ★15M トリガー | +20 |
| レンジ逆張り | +25 (エッジ到達) + 日足整合 +10 + ★トリガー +20 |

**トリガー未発火 → スコアを 70 にキャップ** (`min(score, 70)`)。

#### 5.1.5 SL / TP
- **Long**: SL = min(mt.sma50, mt.last_swing_low) × 0.998 ; TP = lt.resistances[0]
- **Short**: SL = max(...) × 1.002 ; TP = lt.supports[0]
- **Range**: SL = range_bottom × 0.998 (long) / range_top × 1.002 (short) ; TP = 反対エッジ

---

### 5.2 PDH/PDL 手法 (`strategy_pdhl.analyze_pair_pdhl`)

**根拠**: 海外プロップトレーダーの「**ブレイクアウト → リテスト → フラッグ**」型。
**ダマシ回避** がコア。

#### 5.2.1 キーレベル (`_get_pdh_pdl`)
- **PDH** = 前日 (`df_long.iloc[-2]`) の High
- **PDL** = 同上の Low

#### 5.2.2 ロング セットアップ (`_detect_long_setup`)
直近 80 本の 15M 足で順次検出:
1. **ブレイク**: 高値が `PDH × 1.0003` を上抜け (0.03% 以上)
2. **リテスト**: ブレイク後の Low が `PDH ±0.15%` まで戻る
3. **ブルフラッグ**: リテスト以降の最大 5 本で高値・安値が両方切り下がり (±0.05% 許容)
4. **プライスアクション**:
   - ピンバー: 下ヒゲ / レンジ > 50%
   - 包み足: 前足陰線を完全に包む陽線
5. **★ トリガー**: 最新足がフラッグ上限を上抜けて陽線終値

ショートは鏡写し (PDL / ベアフラッグ / 上ヒゲ / 陰の包み足)。

#### 5.2.3 フィルター
- **ノートレードゾーン** (`_no_trade_zone`): `PDL < price < PDH` の狭い領域 (幅 < 0.6%) → 見送り
- **SMT 整合** (`_smt_alignment`): 関連通貨ペアの動きと整合 +5 / 60% 以上逆方向 −5

#### 5.2.4 スコア配点
| 要素 | 配点 |
|---|---|
| ブレイク成立 | +25 |
| リテスト成立 (ダマシ回避) | +20 |
| フラッグ形成 | +15 |
| プライスアクション | pin +8 / engulf +12 / 両方 +15 |
| ★ フラッグブレイク (トリガー) | +20 |
| SMT 整合 | ±5 |

**トリガー未発火 → `min(score, ALERT_THRESHOLD-5)` にキャップ**。

#### 5.2.5 SL / TP
- **Long**: SL = min(flag_lower, PDH) × 0.9985 ; TP = max(直近 80 本高値, price + 1R)
- **Short**: SL = max(flag_upper, PDL) × 1.0015 ; TP = min(直近 80 本安値, price − 1R)

---

### 5.3 Claude Confluence 手法 (`strategy_claude.analyze_pair_claude`)

**根拠 (アカデミック)**:
- Moskowitz/Ooi/Pedersen (2012) Time Series Momentum
- Turtle / Donchian Breakout
- Linda Raschke "Anti" setup
- NR7 / Crabel volatility compression
- Connors mean reversion to 20EMA

**設計**: 6 つのエッジを合流させ、4 つ以上揃った時のみ★点灯。
**RR 1:2 固定** (SL=1.5×ATR, TP=3.0×ATR) で期待値ベースの黒字化を狙う。

#### 5.3.1 6 つのエッジ
| # | 要素 | 関数 | 配点 |
|---|---|---|---|
| 1 | HTF バイアス (日足+4H 両方 EMA50 同方向) | `_htf_bias` | +20 (基礎点) |
| 2 | 4H モメンタム (RSI 50–70 / MACD hist 同方向) | `_mid_momentum` | RSI +8, MACD +7 |
| 3 | 15M ATR 収縮 (直近 5 本 / 100 本平均 < 0.7×) | `_atr_contraction` | < 0.7× → +15 / < 0.9× → +8 |
| 4 | 15M 20EMA プルバック (±0.15% 以内) | `_ema_pullback` | タッチ +15 / 近傍 +6 |
| 5 | 15M RSI 50 再奪取 (反対側から越え) | `_rsi_reclaim` | reclaim +10 / 維持 +5 |
| 6 | ★ Donchian 20 本ブレイク (body ratio > 0.4) | `_donchian_trigger` | +15 |

**満点合計 = 95** (基礎 20 + 15+15+15+10+15 + 4H 5)。実装は `min(score, 100)`。
**トリガー未発火 → `min(score, ALERT_THRESHOLD-5)` にキャップ**。

#### 5.3.2 SL / TP (固定 RR 1:2)
- ATR(14) 算出 (av)、ゼロなら price × 0.002 をフォールバック
- **Long**: SL = price − 1.5×av ; TP = price + 3.0×av
- **Short**: 鏡写し

---

### 5.4 ORZ + PDHL 合意 (`api._build_both_method`)

**合意条件**:
- `orz.direction == pdhl.direction` (none を除く)
- 不一致 → `direction="none"`, score=0 で見送り

**スコア**: 両者の平均、両方 alert 時は +5、1H 整合で ±5。
**SL/TP**: より保守的な側を採用
- SL: long=max(両者) / short=min(両者)
- TP: long=min(両者) / short=max(両者)

**`has_trigger`**: 両者ともトリガー
**`is_alert`**: 両者とも alert

---

### 5.5 ORZ + PDHL + Claude 三方合意 (`api._build_triple_method`)

**合意条件**: 3 手法すべての direction が一致。

**スコア**: 3 者平均、3 者 alert 時は **+10 ボーナス**、1H 整合は同方向 +5 / 逆方向 −8 (やや厳しめ)。
**SL/TP**: 3 者で最も保守的な値。
**`has_trigger`** / **`is_alert`**: 3 者すべてで True の場合のみ。

> 最高勝率ゾーン (`entry_type = "triple_confluence"`)。チャート上で 🏆 表示。

---

## 6. 1H 整合チェック (`api._h1_alignment`)

| direction | 1H regime | delta | reason / warning |
|---|---|---|---|
| long | trend_up | **+5** | "1H 同方向 (上昇トレンド継続)" |
| long | trend_down | **−5** | warning: "1H が逆トレンド - 短期戻し警戒" |
| short | trend_down | **+5** | "1H 同方向 (下降トレンド継続)" |
| short | trend_up | **−5** | warning: 上記同様 |
| any | range | 0 | "1H はレンジ (押し戻し許容)" |
| any | unclear | 0 | — |

`both` と `triple` の合成スコアに加減算 (triple は逆方向時 ×1.5 で厳しめ)。

---

## 7. アラート構造

```
シグナル                          5 メソッド独立計算
  ↓                              orz / pdhl / claude が dict を返却
api/_signal_to_dict
  ├─ orz   (strategy.Signal → dict)
  ├─ pdhl  (analyze_pair_pdhl の dict)
  ├─ claude (analyze_pair_claude の dict)
  ├─ both  = _build_both_method(orz, pdhl, ht)
  └─ triple = _build_triple_method(orz, pdhl, claude, ht)

各 method dict は以下のフィールドを持つ:
  direction      "long" / "short" / "none"
  entry_type     pullback / breakout / range_reversal / pdhl_*_retest
                 / both_confluence / claude_confluence_* / triple_confluence
                 / wait / none
  score          0-100
  price          現在値
  stop_loss      損切目安
  take_profit    利確目標
  has_trigger    ★ 15M トリガー発火フラグ
  is_alert       通知対象フラグ (score ≥ ALERT_THRESHOLD かつ has_trigger)
  reasons        判断根拠 (str list)
  warnings       注意点 (str list)
  pdh / pdl      PDHL 系のみ
```

### アラート発火条件
**`is_alert == True`** = `has_trigger AND score >= ALERT_THRESHOLD (=75) AND direction != "none"`

トリガー未発火だがスコアは高い状態 = 「**セットアップ準備段階**」として
UI に表示され通知は飛ばない。

### スコアキャップ
全手法共通: **`has_trigger == False`** → `score = min(score, threshold - 5)` 程度に制限。
これにより「準備段階だがスコアだけ高い」状態でアラートが鳴ることを防ぐ。

---

## 8. 資金管理ライン (フロントエンド計算)

`frontend/src/components/DetailDrawer.tsx` で計算、Chart.tsx で描画。

### 8.1 数式
```
1R = |entry - stop_loss|
TP_2R = entry ± 2R   (1:2 リスクリワード)
TP_3R = entry ± 3R   (1:3 リスクリワード, プロ推奨)
```

### 8.2 期待値の根拠
```
EV/trade = WinRate × R_target − (1 − WinRate) × 1

RR=2: WinRate ≥ 33.3% でブレークイーブン
RR=3: WinRate ≥ 25%   でブレークイーブン
       WinRate 30% で +0.20R/trade の正期待値
```

### 8.3 ロット計算 (`RiskCalculator.tsx`)
```
pipSize       = JPY クロスなら 0.01、それ以外 0.0001
SL_pips       = |entry − SL| / pipSize
riskJPY       = account × (riskPct / 100)
pipValuePerLot= JPY クロス: 1000 / その他: 10 × USDJPY(155 固定)
推奨 lot      = riskJPY / (SL_pips × pipValuePerLot)
通貨数         = lot × 100,000
```

---

## 9. UI / 通知

### 9.1 公開エンドポイント (`api.py`)
| Method | Path | 説明 |
|---|---|---|
| GET | `/api/health` | 動作確認 |
| GET | `/api/pairs` | 監視対象一覧 |
| GET | `/api/signals` | 全ペア × 5 手法のスナップショット |
| GET | `/api/chart/{symbol}?tf=mid` | OHLC + SMA + 一目雲 (`week/long/mid/h1/short/m5/m1`) |
| GET | `/api/config` | 閾値・更新間隔 |

### 9.2 チャートレイヤ (`frontend/src/components/Chart.tsx`)
- ローソク + SMA20/50/100 + 一目雲 (先行 A/B エリア)
- 価格ライン (右軸ラベル日本語化済み):
  - 前日高値 / 前日安値 (実線 太字)
  - レジ1/2/3, サポ1/2/3 (破線)
  - エントリー (点線)
  - 損切り (1R) / 利確 (構造) (実線)
  - **利確@2R 最低基準** (青破線)
  - **利確@3R 推奨 ★** (金実線 太)
- 操作: マウスホイール拡縮、ドラッグでパン、軸ドラッグでスケール、ピンチ対応
- 右上ボタン: ズームイン (+) / アウト (−) / 全体フィット (↻) / 全画面切替

### 9.2.5 ライブ価格 (Finnhub / OANDA) — 高頻度更新レイヤ
- **データ源**: 2 プロバイダから環境変数で自動選択 (優先度順)
  1. **Finnhub** (`FINNHUB_API_KEY`): 60 req/min・無料・本人確認不要・`/v1/quote?symbol=OANDA:EUR_USD`
  2. **OANDA v20** (`OANDA_API_TOKEN` + `OANDA_ACCOUNT_ID`): 30 req/sec・Practice/Live 両対応
- **取得経路**: ブラウザ → Vercel serverless function (`frontend/src/app/api/live-prices/route.ts`) → プロバイダ
- **更新間隔**: サーバ側がプロバイダのレート制限に応じて推奨値を返す
  - Finnhub: **15 秒** (60/min ÷ 15 並列 ≒ 4 サイクル/min)
  - OANDA: **3 秒** (15 ペア 1 リクエストにまとめて 20 req/min)
- **トークン管理**: 全て **サーバ side env のみ** で保持 (`NEXT_PUBLIC_` を付けない)。
  ブラウザバンドルに含まれず CORS 問題も serverless が解決
- **シンボル変換**: `frontend/src/app/api/live-prices/route.ts` の `YF_TO_BASE` で
  yfinance `USDJPY=X` → 共通形式 `USD_JPY` → 各プロバイダ形式 (`OANDA:USD_JPY` or `USD_JPY`)
- **クライアント**: `frontend/src/lib/oanda.ts` の `useLivePrices(symbols, { intervalMs? })`
  - `intervalMs` 未指定時はサーバの `interval_hint_ms` を採用
  - `LivePrice.tick` で前回比 up/down/flat を取得
  - `provider` で現在のプロバイダ名 (`"finnhub"` / `"oanda"`) を返す
- **アラート**: `frontend/src/lib/liveAlerts.ts` がライブ mid 値が
  PDH / PDL / Entry / SL / TP を **跨いだ瞬間** にブラウザ Notification + Web Audio ビープを発火。
  同一 `pair × levelKind × direction` は **5 分クールダウン** で連射防止
- **シグナル計算は変えない**: ライブ価格は表示と level-cross 検知のみ。
  ORZ/PDHL/Claude の判定は引き続き GitHub Actions の 15 分 cron で更新される

### 9.3 通知チャネル (`config.py` / `alerts.py`)
| 手段 | 設定キー | 制限 |
|---|---|---|
| Beep | `PLAY_SOUND` | Win のみ (winsound) |
| Discord Webhook | `DISCORD_WEBHOOK_URL` | 無料・無制限 |
| LINE Push | `LINE_CHANNEL_ACCESS_TOKEN`, `LINE_USER_ID` | 月 200 通 |
| WhatsApp (CallMeBot) | `WHATSAPP_PHONE`, `WHATSAPP_APIKEY` | 無料 |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | 無料・無制限 |

`alerts.format_signal_message(signal)` で整形してから送信。

### 9.4 GitHub Actions / Vercel
`scripts/build_static.py` が cron で `/api/signals` 相当の JSON を生成 →
`frontend/public/api/*.json` に出力 → Vercel が静的サイトとして配信。
バックエンドサーバー不要の完全無料運用が可能 (`DEPLOY.md` 参照)。

---

## 10. 環境変数 / 主要定数

| 名前 | 既定値 | 場所 |
|---|---|---|
| `ALERT_THRESHOLD` | 75 | `config.py` |
| `REFRESH_SECONDS` | 300 | `config.py` |
| `LONG_INTERVAL/PERIOD` | 1d / 2y | `config.py` |
| `MID_INTERVAL/PERIOD/RESAMPLE` | 1h / 730d / 4h | `config.py` |
| `H1_INTERVAL/PERIOD` | 1h / 60d | `config.py` |
| `SHORT_INTERVAL/PERIOD` | 15m / 60d | `config.py` |
| `USDJPY_FALLBACK` | 155 | `RiskCalculator.tsx` |

---

## 11. AI 向け使用ガイド

このアプリの判断ロジックを他の AI が再利用する際の推奨手順:

1. **入力**: 任意 FX ペアの D1 / 4H / 1H / 15M OHLC (pandas DataFrame)
2. **分析**:
   - `strategy.analyze_pair` で ORZ シグナル
   - `strategy_pdhl.analyze_pair_pdhl` で PDH/PDL シグナル
   - `strategy_claude.analyze_pair_claude` で Confluence シグナル
   - 必要なら `api._build_both_method` / `_build_triple_method` で合意手法を合成
3. **判定**: `is_alert == True` のシグナルだけ採用
4. **資金管理**: SL/TP に加え 1R / 2R / 3R 利確を必ず計算し、
   トレード前に「**この勝率で長期プラスになるか**」を確認
5. **検証**: 同一ロジックをヒストリカルで回し WinRate × R_target − (1-WinRate) > 0 を担保

### 設計上の前提
- yfinance は遅延配信 (15 分〜)、リアルタイム板情報は無し
- 全シグナルは「**確定足ベース**」(未確定の最新バーも含むが、ロジックは shift で対応)
- 経済指標発表やニュースは未考慮 → ファンダメンタル要因はユーザー側で別途確認
- レバレッジ・必要証拠金・スワップは未計算 → ブローカー側で要確認

---

## 12. 拡張・改修ポイント (TODO 候補)

- [ ] BB / Keltner / VWAP など追加インジケーターによる第 4 手法
- [ ] ニュース時刻 (`econoday`/`forexfactory` 等) によるフィルター
- [ ] バックテスト基盤 (現在はライブ評価のみ)
- [ ] WinRate / R_multiple の履歴トラッキング
- [ ] ML ベースの合意重み学習 (現在は等加重平均)

---

*Last updated: 2026-05-13 / 想定読者: 他の AI / 開発者 / アルゴ移植者*
