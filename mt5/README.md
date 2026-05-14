# MT5 Indicator — FX Signal Monitor

MetaTrader 5 のチャート上に **fx-signal-monitor** の 5 手法シグナルを
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
