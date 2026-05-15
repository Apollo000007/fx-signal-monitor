# CLAUDE.md — FX Signal Monitor 引き継ぎ索引

> **For any AI assistant (Claude / ChatGPT / Gemini / Cursor):**
> This file is the project handoff index. Read it **fully first**, then read
> [`docs/SESSION_HANDOFF.md`](docs/SESSION_HANDOFF.md) for the detailed dump.
> 言語は日本語中心 (技術タグは英語)。返答も日本語で行うこと。

---

## プロジェクト概要 (One-liner)

FX シグナルモニター。複数戦略でエントリーシグナルを算出し、Web UI / Telegram /
MT5 EA へ配信する。GitHub Actions cron (5分) → `signals.json` → Vercel CDN。

- **作業ディレクトリ**: `~/dev/fx-signal-monitor` (git clone, 正)
- **本番**: Vercel 自動デプロイ (GitHub push 連動)
- **GitHub**: `Apollo000007/fx-signal-monitor` (branch: `main`)

---

## 絶対ルール (Critical Rules — 違反厳禁)

1. **作業は `~/dev/fx-signal-monitor` のみ。** `~/Downloads/fx-signal-monitor-main`
   は古い zip 展開。**絶対に使わない / 編集しない。**
2. **TRIPLE のロジックは変更禁止。** 具体的には
   `api.py::_build_triple_method(orz, pdhl, claude, ht)` と
   `strategy_claude.py::analyze_pair_claude` を**一切変更しない**
   (ユーザー明示指示)。
3. **`claude` / `both` は削除しない。** UI / 通知 / backtest / paper / MT5 から
   は「ユーザー向け手法」として除外済みだが、**TRIPLE が内部計算で `claude` を
   使う**ため `api.py` の `_compute_signals` / `analyze_pair_claude` は維持。
4. **commit / push はユーザーが明示的に要求した時のみ。** push 前に必ず
   `git pull --rebase origin main` (過去に reject が頻発)。
5. **シークレットをチャットや commit に貼らない**
   (`TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` / Finnhub / OANDA 等)。
   GitHub Secrets / 環境変数経由でのみ扱う。
6. ローカルサーバー (:8000 / :3000) は稼働継続が前提。勝手に停止しない。

---

## アーキテクチャ (Architecture)

```
GitHub Actions cron (5分間隔, self-trigger チェーンで実質維持)
  └─ scripts/build_static.py
       ├─ api._compute_signals()  ← strategy*.py で分析
       ├─ frontend/public/api/signals.json   → Vercel CDN → Web UI / MT5 EA polling
       ├─ frontend/public/api/chart/*.json   → チャート描画
       ├─ 新規アラート検出 → Telegram 通知 (alerts.send_telegram)
       └─ paper_trade.runner.tick()          → 仮想売買 → paper.json (UI 表示)
```

ライブ価格プロバイダは全て遮断 (Finnhub 403 / Yahoo Vercel IP block /
OANDA・Saxo は KYC 離脱)。**現状ライブ価格なし、5分 cron の signals.json で運用。**

---

## 手法ステータス (Method Status)

| 手法 | UI/通知/検証 | 実体 |
|---|---|---|
| `orz` | ✅ 稼働 | `strategy.py::analyze_pair` |
| `pdhl` | ✅ 稼働 | `strategy_pdhl.py` |
| `triple` | ✅ 稼働 | `api.py::_build_triple_method` = ORZ+PDHL+Claude 合議 **(変更禁止)** |
| `dtp` | ✅ 稼働 | `strategy_dtp.py` (Daily Trend Pullback) |
| `claude` | ⛔ 内部のみ | `strategy_claude.py` — TRIPLE が使用。削除禁止 |
| `both` | ⛔ 内部のみ | `api.py` 内部計算でのみ存在 |

UI/通知/backtest/paper の対象は `("orz","pdhl","triple","dtp")` で統一
(`scripts/build_static.py::METHODS_TO_NOTIFY`,
`paper_trade/runner.py::METHODS`, `backtest/engine.py::METHOD_NAMES`)。

---

## バックテスト結論 (60d, 詳細は `backtest/FINDINGS.md`)

| 手法 | 結果 | 判断 |
|---|---|---|
| **TRIPLE** | 5t WR60% PF3.42 +5.3R | 唯一の明確 +EV (構造TP) ★ |
| **DTP** | 集計 -EV だがペア依存大 | **ホワイトリスト運用前提** |
| ORZ / PDHL | -EV (PF<1) | TP/SL 設計に課題 |

**DTP ホワイトリスト**: `AUDJPY, NZDUSD, USDCHF, GBPJPY` で **+32.7R**
(AUD/JPY +13.3R, NZD/USD +11.0R, USD/CHF +4.7R, GBP/JPY +3.7R)。
ZAR/JPY -34.7R が集計を破壊するため、DTP は必ずペア限定で使う。

---

## 主要ファイル (File Map)

| 種別 | パス |
|---|---|
| 戦略 | `strategy.py`(orz) `strategy_pdhl.py` `strategy_claude.py`(TRIPLE内部・変更禁止) `strategy_dtp.py` |
| API | `api.py` (`_compute_signals` / `_build_triple_method`・変更禁止 / `_dtp_to_method_dict`) |
| cron ビルド | `scripts/build_static.py` (`METHODS_TO_NOTIFY`, paper tick 呼び出し) |
| 通知 | `alerts.py` (LINE/WhatsApp/Telegram/Discord) |
| backtest | `scripts/backtest.py` `backtest/engine.py` (`--tp-rr` で R 固定TP) |
| paper trade | `paper_trade/runner.py` `paper_trade/broker.py` (cron 統合済) |
| MT5 | `mt5/Indicators/FXSignal/` `mt5/Experts/FXSignalEA/FXSignalEA.mq5` |
| frontend | `frontend/src/` (Next.js 14, `components/MethodTabs.tsx` 等) |
| ジャーナル | `docs/FX_Trade_Journal.xlsx`(混合) `docs/FX_Manual_Trade_Journal.xlsx`(手法別) |

---

## ローカル起動 (Local Dev)

```bash
# Backend (FastAPI :8000)
cd ~/dev/fx-signal-monitor && nohup python3 -m uvicorn api:app \
  --host 127.0.0.1 --port 8000 > /tmp/fxapi.log 2>&1 &

# Frontend (Next.js :3000, :8000 をプロキシ)
cd ~/dev/fx-signal-monitor/frontend && NEXT_PUBLIC_STATIC_MODE=false \
  nohup npm run start > /tmp/fxnext.log 2>&1 &
```

稼働確認: `lsof -ti :8000` / `lsof -ti :3000`。
cron ビルド手動実行: `python3 scripts/build_static.py`。
backtest 例: `python3 scripts/backtest.py --days 60 --tp-rr 3`。

---

## ドキュメント索引 (Doc Index)

| ファイル | 内容 |
|---|---|
| [`docs/SESSION_HANDOFF.md`](docs/SESSION_HANDOFF.md) | **詳細引き継ぎダンプ (まず読む)** |
| [`DEPLOY.md`](DEPLOY.md) | デプロイ手順 (GitHub / Vercel / Telegram) |
| [`METHODOLOGY.md`](METHODOLOGY.md) | 各手法のロジック説明 (AI 可読) |
| [`backtest/FINDINGS.md`](backtest/FINDINGS.md) | バックテスト数値・TP 比較 |
| [`docs/TRADE_JOURNAL_GUIDE.md`](docs/TRADE_JOURNAL_GUIDE.md) | 混合ジャーナル使い方 |
| [`docs/MANUAL_JOURNAL_GUIDE.md`](docs/MANUAL_JOURNAL_GUIDE.md) | 手法別手動ジャーナル使い方 |

---

## 引き継ぎ手順 (Handoff Procedure)

- **新しい Claude Code セッション** → このファイルは自動ロードされる。
  追加操作不要。続けて `docs/SESSION_HANDOFF.md` を読めば完全に把握できる。
- **他 AI (ChatGPT / Gemini / Cursor)** → ユーザーは次を指示:
  > 「リポジトリ直下の `CLAUDE.md` と `docs/SESSION_HANDOFF.md` を全文読んで、
  >  絶対ルールを守って作業して」
- **次にやること (Next Step)**:
  1. ユーザーが MT5 EA で **2 週間 Demo トレード** (推奨: `UseTriple=true` +
     `UseDTP=true`, `TradingPairs=AUDJPY,NZDUSD,USDCHF,GBPJPY`)。
  2. 2 週間後、Demo の **規律スコア (S/A/B/C/D)** と損益を持参 →
     backtest と Live の乖離を検証し、戦略の取捨選択を判断。

## プロとしての結論 (ユーザー合意済み)

- 「確実に勝てる手法」は存在しない。再現性ある +EV = トレンドフォロー
  (TRIPLE / DTP) + 厳格リスク管理 + 規律。
- 利益の 80% は手法でなく資金管理・規律・心理。
- 5-10 トレードでは結論不可。最低 100 トレード必要。
