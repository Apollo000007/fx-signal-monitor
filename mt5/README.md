# MT5 — FX Signal Monitor

MetaTrader 5 に fx-signal-monitor のシグナルを連動させる **2 種類** のツール:

| ツール | 内容 | 自動売買 |
|---|---|---|
| **FXSignal (Indicator)** | チャート上にシグナル・ライン・パネルを表示 | ❌ なし |
| **FXSignalEA (Expert Advisor)** | シグナル発火時に自動で発注 + ポジション管理 | ✅ あり |

両者は同じ仕組み (Vercel signals.json を WebRequest でポーリング) で動き、
**Python ロジックが単一の真実** として共有されます。

📖 **EA のセクションは下にあります** ([→ FXSignalEA Auto-Trading](#fxsignalea-自動売買-ea))

---

# 📊 FXSignal Indicator (視覚化)

チャート上に **fx-signal-monitor** の 5 手法シグナルを
ライブで表示するインディケータです (発注機能なし、視覚化のみ)。

```
┌──────────────────────────────────────────────────────────────┐
│ FX SIGNAL · USD/JPY                                          │
│ 4H: 上昇トレンド  明瞭度 78/100                              │
│ [triple] ▲ LONG  Score 85/100  ★ ALERT                      │
│ Entry : 157.78                                               │
│ 損切り: 157.40  (1R)                                         │
│ 利確 : 158.50  (構造)                                        │
│ ★3R  : 158.92  (推奨)                                        │
│ ── 5 手法スコア ──                                           │
│ orz...   75  long  ★                                         │
│ pdhl..   72  long  ▶                                         │
│ both..   73  long  ★                                         │
│ claude   68  long  ·                                         │
│ triple   85  long  ★                                         │
│ ── 根拠 ──                                                   │
│ • 4H 上昇トレンド / 明瞭度 78/100                            │
│ • 日足も同方向トレンド (環境◎)                              │
│ • 4H 押し目/戻り目 (SMA50)                                   │
│ • ★15Mトリガー: 安値切り上げ+陽線                            │
│ API: OK · USD/JPY · 取得 12:34                               │
└──────────────────────────────────────────────────────────────┘
```

加えてチャート上に水平線で:
- **前日高値 / 前日安値** (緑/赤・実線)
- **エントリー** (シアン・点線、alert 時のみ)
- **損切り 1R** (赤・太線)
- **利確 構造** (緑・太線)
- **★ 利確 3R 推奨** (金・太線)

そして発火バーに **矢印 (▲/▼)** を表示します。

---

## インストール手順

### 1. ファイルを MT5 の Indicators フォルダにコピー

MT5 を開いて **File → Open Data Folder** をクリック。`MQL5/Indicators/` フォルダが開きます。

以下のフォルダ構成をそのままコピーしてください:

```
MQL5/
└── Indicators/
    └── FXSignal/
        ├── FXSignal.mq5
        └── Include/
            └── JsonExtract.mqh
```

### 2. WebRequest の URL を許可

MT5 メニュー → **Tools → Options → Expert Advisors** タブ:

1. ✅ **Allow WebRequest for listed URL** にチェック
2. 下の URL リストに以下を **1 行追加**:

```
https://fx-signal-monitor.vercel.app
```

3. **OK** で閉じる

### 3. インディケータをコンパイル

1. MT5 内蔵エディタ **MetaEditor** を開く (F4 キー)
2. 左の Navigator で `Indicators/FXSignal/FXSignal.mq5` をダブルクリック
3. **Compile** ボタン (F7 キー) を押す
4. エラーが出なければ完了。Errors タブが空ならOK

### 4. チャートにアタッチ

1. MT5 で任意の通貨ペア (例: USDJPY) のチャートを開く
2. 左の Navigator → Indicators → Custom → **FXSignal** をダブルクリック (またはチャートにドラッグ)
3. 入力パラメータ画面で必要なら設定変更 → **OK**
4. 数秒待つと API から取得完了し、画面左上にパネルが表示される

---

## 入力パラメータ

| パラメータ | 既定値 | 説明 |
|---|---|---|
| `ApiUrl` | `https://fx-signal-monitor.vercel.app/api/signals.json` | signals.json の URL。自分の Vercel デプロイで上書き可 |
| `RefreshSec` | `60` | API ポーリング間隔 (秒) |
| `AutoMapSymbol` | `true` | チャート通貨 `USDJPY` を `USD/JPY` に自動変換 |
| `PrimaryMethod` | `triple` | 主軸表示する手法 (orz / pdhl / both / claude / triple) |
| `ShowSMA20/50/100` | `true` | 移動平均線の表示 |
| `ShowCloud` | `true` | 一目均衡表の雲 |
| `ShowPDHL` | `true` | 前日高値・安値ライン |
| `ShowSignalLines` | `true` | Entry / SL / TP ライン (alert 時のみ) |
| `Show2R3RLines` | `true` | 資産管理 2R / 3R 利確ライン |
| `ShowPanel` | `true` | 左上の情報パネル |
| `ShowArrow` | `true` | 発火バー上の矢印 (▲/▼) |
| `PanelX`, `PanelY`, `PanelW`, `FontSize` | 12, 24, 360, 9 | パネル配置・サイズ |

---

## 動作の仕組み

```
   MT5 チャート
      │
      ↓ WebRequest GET (60 秒ごと)
   https://fx-signal-monitor.vercel.app/api/signals.json
      │
      ↓ JSON レスポンス
   FXSignal.mq5
      ├─ 現在チャートの通貨ペアに対応するレコード抽出
      ├─ 5 手法 (orz/pdhl/both/claude/triple) のスコア / Direction / Alert 状態
      ├─ 主軸手法の Entry / SL / TP / Reasons
      ├─ 2R / 3R 利確を |Entry - SL| から再計算
      └─ Chart Object として描画
```

- **同期性**: Vercel の `signals.json` は GitHub Actions cron (5 分間隔) で更新
- **遅延**: cron 発火 → Vercel デプロイ → 60 秒ポーリングで合計 **約 5-10 分後** に MT5 反映
- **データ整合性**: Web ダッシュボードと MT5 で完全に同じ値が見える

---

## チャートに合わせた使い方

### M15 チャート (15 分足) を推奨

シグナルロジックは **15M トリガー** ベースなので、15 分足チャートが最も整合性が高いです。

### 推奨レイアウト

1. M15 チャートを 15 通貨ペア × 別タブで開く
2. 各タブに FXSignal インディケータをアタッチ
3. パネルが ★ ALERT になっているペアを優先監視
4. SL / 3R-TP ラインの位置を見てエントリーを判断

### 手動トレード時の手順

1. パネルが **★ ALERT** 状態 (主軸手法のスコアが閾値以上 + トリガー発火) になっていることを確認
2. **Entry** ラインの価格付近で **Direction (LONG/SHORT)** の方向にエントリー
3. **損切り (1R)** に Stop Loss を、**★ 利確@3R** に Take Profit を設定
4. PDH/PDL に到達したらポジション保有時はトレーリングを検討

---

## よくある質問

### Q. パネルに「API err」と出る
A. WebRequest URL の許可設定を確認してください (上記ステップ 2)。`Tools → Options → Expert Advisors` で `https://fx-signal-monitor.vercel.app` を URL リストに追加する必要があります。

### Q. パネルに「ペア XXX が signals.json に見つからない」と出る
A. MT5 のチャート通貨が fx-signal-monitor の監視 15 ペアに含まれていない場合に出ます。`config.py` の `PAIRS` に対応する 15 通貨 (USD/JPY, EUR/USD, GBP/USD など) のチャートを使ってください。

`AutoMapSymbol=true` でブローカー固有のサフィックス (`.m`, `.pro` 等) は自動除去されますが、特殊な命名規則 (例: `USDJPY-ECN`) の場合は手動で `_Symbol` を変えるか、`AutoMapSymbol=false` にしてチャート名を `USD/JPY` 等に直接設定。

### Q. SMA や雲が出ない
A. SMA は MT5 内蔵 `iMA()` を使うので問題なく出るはずですが、`indicator_chart_window` ではない別のサブウィンドウに表示されます。チャート右側の **Indicators List** から確認してください。
※ 完全に同じスタイル (色・太さ) で表示するには、別途 SMA を手動でアタッチする方が綺麗な場合もあります。

### Q. 自前 Vercel デプロイの URL に切り替えたい
A. インディケータの **`ApiUrl`** 入力を自分の URL (例: `https://my-fx.vercel.app/api/signals.json`) に変更し、その URL を MT5 の WebRequest 許可リストに追加してください。

### Q. EA として自動売買にしたい
A. 本ファイルは **インディケータ (発注機能なし)** です。自動売買 EA への発展は `METHODOLOGY.md` の Phase C 計画 (MQL5 フル移植) に詳細があります。または、本インディケータをベースに `OrderSend()` を追加することで簡易 EA 化も可能 (自己責任で)。

### Q. シグナルの精度を上げたい
A. シグナル生成は Python 側 (`scripts/build_static.py` + `strategy*.py`) で行われています。ロジック調整は Python リポジトリで実施し、GitHub Actions cron が走れば MT5 にも自動反映されます。

---

## トラブルシューティング

### デバッグログを見る方法
MT5 の **Toolbox → Experts** タブを開くと、`[FXSignal]` プレフィックスのログが出力されます:

```
[FXSignal] API err: HTTP=-1 MQL=4014 (URL を WebRequest 許可済?)
[FXSignal] ペア USD/JPY が signals.json に見つからない
[FXSignal] OK · USD/JPY · 取得 12:34
```

### MQL5 エラーコード
| コード | 意味 | 対処 |
|---|---|---|
| 4014 | WebRequest 関数が許可されていない | Tools → Options → Expert Advisors で URL 許可 |
| 4060 | 関数の使用が許可されていない | EA 全般を許可する設定をチェック |
| -1 (HTTP) | サーバ到達不可 | URL 綴り間違い or ネット未接続 |
| 404 | URL が見つからない | `ApiUrl` の綴りを確認 |
| 503 | サーバエラー | Vercel デプロイ状態確認、Python 側のログ確認 |

---

## ファイル構成

```
mt5/Indicators/FXSignal/
├── FXSignal.mq5            メインインディケータ (約 450 行)
└── Include/
    └── JsonExtract.mqh     軽量 JSON フィールド抽出 (約 150 行)
```

---

## ライセンス / 注意

- 本インディケータは **発注を行いません**。エントリー・決済は手動で実施してください
- シグナル精度は本家 fx-signal-monitor の `strategy*.py` に依存します
- 過去のバックテスト結果と将来の実トレード結果は一致しません (相場の非定常性)
- 必ず Demo 口座で動作確認後に Live で使用してください

---

# 🤖 FXSignalEA (自動売買 EA)

`is_alert=True` のシグナル発火時に **自動でロット計算 → 成行発注 → SL/TP 設定**
までを行う Expert Advisor (EA)。Python ロジックは変更不要で、Vercel signals.json
をポーリングするだけで動作します。

## ⚠️ 重要な事前理解

- **Demo 口座で 1〜2 週間運用してから Live へ移行** することを強く推奨します
- **必ず最初は `DryRun=true` で動作確認** (発注せず "OPEN" ログだけ出力)
- バックテスト (Phase A) で **唯一の +EV だった `triple` 手法だけ** が初期設定で有効
- 1 トレードあたりのリスクは **0.5% に抑えめ** に設定済み (調整可)
- **同時建玉 5 件まで、日次損失 3% 超で自動停止**

## ファイル構成

```
mt5/Experts/FXSignalEA/
├── FXSignalEA.mq5            メイン EA (~350 行)
└── Include/
    ├── JsonExtract.mqh       signals.json パーサ (Indicator と共用)
    ├── RiskMgmt.mqh          ロット計算 / 日次損益追跡
    └── TradeOps.mqh          発注ラッパ (CTrade ベース) + Magic Number 管理
```

## インストール手順

### 1. ファイルを MT5 の Experts フォルダにコピー

MT5 → **File → Open Data Folder** で開いたフォルダの `MQL5/Experts/` 配下に
`FXSignalEA/` フォルダごとコピー:

```
MQL5/
└── Experts/
    └── FXSignalEA/
        ├── FXSignalEA.mq5
        └── Include/
            ├── JsonExtract.mqh
            ├── RiskMgmt.mqh
            └── TradeOps.mqh
```

### 2. MT5 の設定で 2 つの許可

**Tools → Options → Expert Advisors**:

1. ✅ **Allow Algorithmic Trading** (自動売買全般を許可)
2. ✅ **Allow WebRequest for listed URL** + 以下を追加:
   ```
   https://fx-signal-monitor.vercel.app
   ```

### 3. コンパイル

MetaEditor (F4) で `Experts/FXSignalEA/FXSignalEA.mq5` を開き、**F7** でコンパイル。
Errors タブが空なら成功。

### 4. チャートにアタッチ

1. 任意の通貨ペアチャート (どれでも可、EA は内部で 15 ペア全部を見る) を開く
2. 左 Navigator → Expert Advisors → **FXSignalEA** をチャートにドラッグ
3. パラメータ画面が出たら **必ず以下を確認**:
   - **EnableTrading = false** (まず動作確認、後で true に)
   - **DryRun = true** (発注せずログだけ出力)
   - **AccountRiskPercent = 0.5** (0.5% リスク)
   - **UseTriple = true**, 他 = false (triple のみ取引)
4. **OK** → 数秒後、Toolbox の Experts タブにログが出始める

### 5. 動作確認 (DryRun)

数分待つと Experts タブに以下のようなログが出ます:

```
[FXSignalEA] init: 15 pairs, methods=TRIPLE , risk=0.50%, dryrun=ON, trading=OFF
[FXSignalEA] [DRYRUN] USD/JPY triple long score=85 entry=157.78 SL=157.40 TP=158.92 lot=0.10 spread=0.8p
[FXSignalEA] 時間外 (週末/休場) - skip   ← 週末
```

これが見えていれば **シグナル取得・ロット計算は OK**。実発注のみ無効化されています。

### 6. 実発注を有効化 (Demo 口座のみ!)

入力パラメータを変更:

| 段階 | EnableTrading | DryRun | 効果 |
|---|---|---|---|
| 観察 | false | (任意) | 何もしない |
| ログ確認 | true | true | "DRYRUN" ログだけ出る、発注なし |
| **デモ運用** | **true** | **false** | **実発注** ← Demo 口座で! |
| 本番 (慎重に) | true | false | Live 口座で実発注 |

最初は **必ず Demo 口座で 1〜2 週間** 動作確認してください。

## 入力パラメータ詳細

### ━━━ 1. 基本設定 ━━━

| パラメータ | 既定値 | 説明 |
|---|---|---|
| `EnableTrading` | **`false`** | ★ 自動売買マスタースイッチ |
| `DryRun` | **`true`** | ★ true なら実発注せずログのみ |
| `ApiUrl` | `https://fx-signal-monitor.vercel.app/api/signals.json` | signals.json URL |
| `RefreshSec` | `60` | API ポーリング間隔 (秒) |
| `MagicBase` | `880000` | 建玉に振る magic 番号の基点。他 EA と被らない値にする |

### ━━━ 2. 対象通貨ペア ━━━

| パラメータ | 既定値 | 説明 |
|---|---|---|
| `TradingPairs` | `USDJPY,EURUSD,...` (15 ペア) | カンマ区切りで監視対象 |
| `AutoMapSymbol` | `true` | ブローカーのサフィックス (`.m`, `.pro` 等) を自動付与 |

### ━━━ 3. 有効化する手法 ━━━

| パラメータ | 既定値 | 推奨設定 |
|---|---|---|
| `UseORZ` | `false` | バックテスト PF 0.58 で −EV、まず無効 |
| `UsePDHL` | `false` | バックテスト PF 0.91 で わずか −EV、無効 |
| `UseBoth` | `false` | PF 0.40 で −EV、無効 |
| `UseClaude` | `false` | PF 0.77 で −EV、無効 |
| `UseTriple` | **`true`** | **PF 3.42 で唯一の +EV、推奨** |

→ Phase B で蓄積したペーパートレード結果を見ながら、有効化する手法を増減してください。

### ━━━ 4. リスク・資金管理 ━━━

| パラメータ | 既定値 | 説明 |
|---|---|---|
| `AccountRiskPercent` | `0.5` | 1 トレードあたりのリスク% (口座残高比) |
| `MaxConcurrentTrades` | `5` | 同時建玉上限。それ以上は新規見送り |
| `MaxDailyLossPercent` | `3.0` | 当日損失 3% 超 → 新規エントリー停止 (翌日リセット) |
| `UseTP3R` | `true` | true: 3R 利確 (推奨)、false: signals.json の構造的 TP |
| `MaxSpreadPips` | `3.0` | スプレッド広い時は見送り |
| `SlippagePoints` | `30` | 許容スリッページ (points; 1 pip = 10 points で 5 桁) |

**リスク% の感覚**:
- 100 万円口座で `0.5%` → 1 トレード最大損失 ¥5,000
- 5 トレード並列 → 最大 −¥25,000 (= −2.5%)
- 日次損失リミット 3% → −¥30,000 で自動停止

### ━━━ 5. 取引時間ガード ━━━

| パラメータ | 既定値 | 説明 |
|---|---|---|
| `UseTimeGuard` | `true` | 週末・休場時間は禁止 |
| `WeekStart_Hour` | `22` | 日曜 22:00 UTC (= 月曜 7:00 JST) から取引解禁 |
| `WeekEnd_Hour` | `21` | 金曜 21:00 UTC (= 土曜 6:00 JST) で取引終了 |

土曜は完全休止。NY クローズ後の流動性低い時間帯を避けます。

## 動作の仕組み

```
   60秒ごとに ↓
   ┌──────────────────────────────────────────────────────┐
   │ 1. 取引時間チェック (週末スキップ)                    │
   │ 2. 日次損失リミット (-3% 超なら停止)                  │
   │ 3. 同時建玉数チェック (5 件以上なら新規見送り)       │
   │ 4. signals.json を WebRequest GET                     │
   │ 5. 各ペアについて:                                    │
   │     a. スプレッドチェック                              │
   │     b. 既存建玉あれば同 pair × method はスキップ     │
   │     c. is_alert=True → ロット計算 → 発注              │
   │        - SL: signals.json の値                        │
   │        - TP: 3R 計算値 (UseTP3R=true) or 構造値       │
   │        - magic = MagicBase + pair_idx*10 + method_idx │
   │ 6. 次の RefreshSec まで待機                           │
   └──────────────────────────────────────────────────────┘
```

## Magic Number の設計

| pair_index | method_index | magic |
|---|---|---|
| 0 (USDJPY) | 0 (orz) | 880000 |
| 0 (USDJPY) | 4 (triple) | 880004 |
| 1 (EURUSD) | 4 (triple) | 880014 |
| ... | ... | ... |
| 14 (EURGBP) | 4 (triple) | 880144 |

→ 同 pair × 同 method の重複建玉を確実に防止。
→ 他 EA / 手動注文と magic が被らないので**独立管理**。

## 安全装置まとめ

| 装置 | 動作 |
|---|---|
| **EnableTrading** | マスタースイッチ。false で何も起きない |
| **DryRun** | 注文を出さずログのみ |
| **MaxConcurrentTrades** | 同時建玉数を上限化 |
| **MaxDailyLossPercent** | 当日損失閾値で新規停止 |
| **MaxSpreadPips** | 異常スプレッド時は見送り (指標発表時等) |
| **UseTimeGuard** | 週末・休場時間は禁止 |
| **Magic Number** | この EA 建玉だけ管理、他と競合せず |
| **SL/TP サーバ側** | PC 落ちても約定する (broker サーバが管理) |

## よくある質問

### Q. EA が動いてるのにポジションが開かない
A. 以下を順にチェック:
1. **EnableTrading = true** か?
2. **DryRun = false** か? (DryRun=true は発注しない)
3. **MT5 ツールバー右上の AutoTrading ボタンが緑** か?
4. Experts タブで `is_alert` が出ているシグナルがあるか?
5. ペアが TradingPairs に含まれているか?
6. スプレッドが MaxSpreadPips を超えていないか?

### Q. ロットが思ったより大きい/小さい
A. `AccountRiskPercent` を変更してください。0.1〜1.0 の範囲で調整。
口座残高が大きい場合、SL 距離が短いとロットが膨らみすぎることがあるので注意。

### Q. 既存ポジションを EA に管理させたい
A. できません。Magic Number 一致でのみ管理対象になります。
既存手動ポジションはそのまま手動管理してください。

### Q. 複数チャートに同じ EA をアタッチしてもいいか
A. **NG**。同じ MagicBase で動く EA を複数走らせると重複発注になります。
1 つのチャートにアタッチするだけで全 15 ペアを内部で監視します。

### Q. ストラテジーテスターでバックテストしたい
A. 本 EA は `WebRequest` を使うため MT5 内蔵のストラテジーテスターでは
**動作しません** (テスター内部では WebRequest が呼べない)。
バックテストは Python 側の `scripts/backtest.py` (Phase A) で実施してください。

### Q. EA が落ちたら / PC が落ちたらどうなる?
A. SL / TP は **MT5 サーバ側** に乗っているので、約定は自動的に行われます。
EA が止まっても **既存ポジションの決済は問題なく実行** されます。
ただし新規エントリーは EA 再起動まで止まります。

### Q. ロスカットされたくない
A. `MaxDailyLossPercent` を厳しめに設定 (例 2.0)、`AccountRiskPercent` を下げる
(例 0.2) ことで、日次最大損失を強制制限できます。
ストップカット手前で EA が新規停止するため、追証リスクは大幅に下がります。

## トラブルシューティング

### MT5 Experts タブのログの読み方

```
[FXSignalEA] init: 15 pairs, methods=TRIPLE , risk=0.50%, dryrun=ON, trading=OFF
[FXSignalEA] [DRYRUN] USD/JPY triple long score=85 entry=157.78 SL=157.40 TP=158.92 lot=0.10
[FXSignalEA] 同時建玉上限 5 到達 - skip
[FXSignalEA] 日次損失 -3.21% (限度 3.00%) - 新規エントリー停止
[FXSignalEA] USD/JPY スプレッド 5.2pips > 3.0 - skip
[FXSignalEA] API エラー: HTTP=-1 MQL=4014 (URL を WebRequest 許可済?)
[TradeOps] OPEN USDJPY long lot=0.10 entry=157.78 SL=157.40 TP=158.92 magic=880004 ticket=12345
[TradeOps] 注文失敗: USDJPY long lot=0.10 ret_code=10006 (Common error)
```

### よくある MT5 エラーコード

| ret_code | 意味 | 対処 |
|---|---|---|
| 10004 | Re-quote | スリッページ拡大 (SlippagePoints) |
| 10006 | Request rejected | ブローカー側で発注禁止? Demo/Live 確認 |
| 10014 | Invalid volume | ロットがブローカー制約から外れた、桁数確認 |
| 10015 | Invalid price | SL/TP が現在価格に近すぎる (Stop Level 違反) |
| 10016 | Invalid stops | 同上 |
| 10018 | Market closed | 取引時間外 |
| 10019 | Not enough money | 証拠金不足 |
| 10027 | Auto-trading disabled | AutoTrading ボタンを ON に |

## ライセンス / 免責

- 本 EA は **教育・検証目的** に提供されます
- **損失が発生する可能性があり、その全責任はユーザー本人** に帰属します
- **必ず Demo 口座で十分な動作確認** を行ってください
- 過去バックテストの結果が将来の利益を保証するものではありません
- ライブ運用時は必ず資金管理ルール (`AccountRiskPercent`, `MaxDailyLossPercent`) を
  小さく設定し、徐々に増やしてください
- スリッページ・スプレッド拡大・約定遅延などにより、バックテストとは異なる結果になります
