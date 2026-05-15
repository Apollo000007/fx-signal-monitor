# セッション引き継ぎサマリ (2026-05-15)

次の AI / 自分が続きから作業するための圧縮メモ。

## プロジェクト概要

FX シグナルモニター。`~/dev/fx-signal-monitor` が git 管理クローン
(GitHub: `Apollo000007/fx-signal-monitor`、Vercel 自動デプロイ)。
※ `~/Downloads/fx-signal-monitor-main` は古い zip 展開、**使わない**。

## システム構成 (完成済み)

```
GitHub Actions cron (5分, self-trigger チェーンで実質5分維持)
  → strategy*.py 分析 → signals.json → Vercel CDN
  → Telegram 通知 (Bot 設定済み、TELEGRAM_BOT_TOKEN/CHAT_ID)
  → MT5 Indicator / EA が signals.json をポーリング
```

## 手法 (Method) の現状

- **稼働中 (UI/通知/検証に出る): `orz` / `pdhl` / `triple` / `dtp`**
- **裏方 (UI から削除済、TRIPLE 内部計算でのみ使用): `claude` / `both`**
  - `api.py` `_build_triple_method(orz,pdhl,claude,ht)` は無変更で claude を使う
  - `analyze_pair_claude` は `_compute_signals` で計算継続
  - **TRIPLE ロジックは絶対に変更しないこと** (ユーザー指示)

## バックテスト結果 (60d, `backtest/FINDINGS.md` 詳細)

| 手法 | 集計 | 備考 |
|---|---|---|
| TRIPLE | 5t WR60% PF3.42 +5.3R ★ | 唯一の明確 +EV (構造TP) |
| DTP | 254t 集計 -EV だが**ペア依存激しい** | 下記 |
| ORZ/PDHL | -EV (PF<1) | TP/SL設計に課題 |

**DTP のペア別 (重要)**: AUD/JPY +13.3R, NZD/USD +11.0R, USD/CHF +4.7R,
GBP/JPY +3.7R = 4ペアで **+32.7R**。ZAR/JPY -34.7R が集計を破壊。
→ **DTP はホワイトリスト運用前提**: `AUDJPY,NZDUSD,USDCHF,GBPJPY`

## 主要ファイル

| 種別 | パス |
|---|---|
| 戦略 | `strategy.py`(orz) `strategy_pdhl.py` `strategy_claude.py` `strategy_dtp.py` |
| API | `api.py` (_compute_signals, _build_triple_method) |
| cron | `scripts/build_static.py` (METHODS_TO_NOTIFY) |
| backtest | `scripts/backtest.py` `backtest/engine.py` (`--tp-rr` で R 固定TP可) |
| paper trade | `paper_trade/runner.py` `broker.py` (cron 統合済、戦績→`frontend/public/api/paper.json`) |
| MT5 | `mt5/Indicators/FXSignal/` `mt5/Experts/FXSignalEA/` (README にセットアップ) |
| ジャーナル | `docs/FX_Trade_Journal.xlsx` (混合) `docs/FX_Manual_Trade_Journal.xlsx` (手法別) |

## ローカルサーバー (現在稼働中)

- Backend: `uvicorn api:app` :8000 (pid は `lsof -ti :8000` で確認)
- Frontend: `npm run start` :3000 (`NEXT_PUBLIC_STATIC_MODE=false` で :8000 プロキシ)
- 起動コマンド:
  ```bash
  cd ~/dev/fx-signal-monitor && nohup python3 -m uvicorn api:app --host 127.0.0.1 --port 8000 > /tmp/fxapi.log 2>&1 &
  cd ~/dev/fx-signal-monitor/frontend && NEXT_PUBLIC_STATIC_MODE=false nohup npm run start > /tmp/fxnext.log 2>&1 &
  ```

## ライブ価格プロバイダの結論

- Finnhub 無料: forex /quote が 403 → 不可
- Yahoo 直: Vercel datacenter IP がブロック → 不可
- OANDA/Saxo: 本人確認の壁でユーザー離脱
- **現状: ライブ価格なし、5分 cron の signals.json のみ。これで運用**

## 次のステップ (ユーザー予定)

1. **明日から 2 週間 Demo トレード** (MT5 EA)
   - 推奨設定: `UseTriple=true` + `UseDTP=true`、
     `TradingPairs=AUDJPY,NZDUSD,USDCHF,GBPJPY`、`DryRun` で1日確認後 `false`
   - 手動分は `docs/FX_Manual_Trade_Journal.xlsx` の手法別シートに記録
2. 2 週間後、Demo の **規律スコア(S/A/B/C/D)** と損益を持参
   → backtest と Live の乖離を検証、戦略の取捨選択判断

## プロとしての結論 (ユーザーに伝え済み)

- 「確実に勝てる手法」は存在しない
- 再現性ある +EV = トレンドフォロー(TRIPLE/DTP) + 厳格リスク管理 + 規律
- 利益の 80% は手法でなく資金管理・規律・心理
- 5-10 トレードでは何も結論できない。最低 100 トレード必要
- DTP は AUD/JPY・NZD/USD で最有望

## 直近の git 状態

main ブランチ最新コミット: claude/both を UI/通知/検証から削除
(TRIPLE 内部計算は維持)。Vercel 自動デプロイ済み。
