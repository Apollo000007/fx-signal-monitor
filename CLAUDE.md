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
2. **TRIPLE: SL/TP は変更可 (2026-05-18 ユーザー許可)。** 当初「TRIPLE 全面
   変更禁止」だったが、ユーザーが「TRIPLE も損切り/利確ラインを変更して
   構わない」と明示。よって `api.py::_build_triple_method` 等の **SL/TP 算出は
   資産管理方針 (最低2R/推奨3R) に合わせて変更してよい**。ただし合議の
   方向判定 (ORZ+PDHL+Claude の一致条件) など中核は合意なく変えない。
   `strategy_claude.py::analyze_pair_claude` も TRIPLE が依存するので
   挙動を変える場合は影響 (backtest/paper) を必ず確認。
3. **`claude` / `both` は削除しない。** UI / 通知 / backtest / paper / MT5 から
   は「ユーザー向け手法」として除外済みだが、**TRIPLE が内部計算で `claude` を
   使う**ため `api.py` の `_compute_signals` / `analyze_pair_claude` は維持。
4. **commit / push はユーザーが明示的に要求した時のみ。** push 前に必ず
   `git pull --rebase origin main` (過去に reject が頻発)。
5. **シークレットをチャットや commit に貼らない**
   (`TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` / Finnhub / OANDA 等)。
   GitHub Secrets / 環境変数経由でのみ扱う。
6. ローカルサーバー (:8000 / :3000) は稼働継続が前提。勝手に停止しない。
7. **RRポリシ**: 全シグナルの TP は最低2R (`risk.min_rr_tp`)。1:1 を作らない。
8. **EVゲート**: alert は `ev_whitelist.is_pair_allowed(method,pair)` を通る +EV の
   (手法,ペア) のみ (TRIPLE常時許可 / DTP=証拠4ペア∪白 / PDHL・ORZは降格)。

---

## ⚠ 重要ポリシ (2週間デモ ポストモーテム 2026-06)

実トレードがRR1:1で実質トントンだった反省から:
- **利確は最低2R**。`risk.py::min_rr_tp` が signals.json/Telegram/paper/MT5 の
  実値まで保証 (表示だけでなく実体)。手動執行も最低2R、推奨3R、損小利大。
- **+EV 実証 (手法,ペア) のみ alert**。`ev_whitelist.py` + `state/ev_whitelist.json`
  (生成: `scripts/backtest.py --emit-whitelist --min-rr 2`)。EUR/USD等のDTPは出ない。
- **通知は triple/dtp/pa に集中**。PDHL/ORZ は UI「参考」表示 (降格)。
- **相関キャップ**: 1サイクル最大4件・同一通貨最大1件 (`detect_new_alerts`)。
- 詳細: [`docs/POSTMORTEM_2W.md`](docs/POSTMORTEM_2W.md)。

---

## アーキテクチャ (Architecture)

```
GitHub Actions cron (5分間隔, self-trigger チェーンで実質維持)
  └─ scripts/build_static.py
       ├─ api._compute_signals()  ← strategy*.py で分析
       ├─ frontend/public/api/signals.json   → Vercel CDN → Web UI / MT5 EA polling
       ├─ frontend/public/api/chart/*.json   → チャート描画
       ├─ strategy_pa.analyze_pair_pa()      → pa 手法 (ローソク足パターン+EV白)
       ├─ news_calendar.build_calendar_payload() → calendar.json (経済指標+リスク)
       ├─ 新規アラート検出 → Telegram 通知 (alerts.send_telegram, 利確は最低2R/3R)
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
| `pa` | ✅ 稼働 | `strategy_pa.py`+`patterns.py` (ローソク足+チャートパターン。確定足+上位足+節目+次足確認+EVホワイトリスト) |
| `dtp` | ✅ 稼働(4ペア限定) | EVゲートで AUD/JPY・NZD/USD・USD/CHF・GBP/JPY のみ alert |
| `pdhl` | 🔻 参考(降格) | `strategy_pdhl.py`。旧1:1で-EV。UI表示のみ・alert無し |
| `orz` | 🔻 参考(降格) | `strategy.py`。不安定TPで-EV。UI表示のみ・alert無し |
| `claude` | ⛔ 内部のみ | `strategy_claude.py` — TRIPLE が使用。削除禁止 |
| `both` | ⛔ 内部のみ | `api.py` 内部計算でのみ存在 |

UI/通知/backtest/paper の対象は `("orz","pdhl","triple","dtp","pa")` で統一
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
| cron ビルド | `scripts/build_static.py` (`METHODS_TO_NOTIFY`, `write_calendar`, paper tick) |
| PA パターン | `patterns.py` (検出器+メタ) `strategy_pa.py` (大前提ゲート) `scripts/backtest_pa.py` (EVホワイトリスト→`state/pa_whitelist.json`) `backtest/PA_FINDINGS.md` |
| RR/EVポリシ | `risk.py` (TP最低2R床) `ev_whitelist.py` (手法×ペアEVゲート) `state/ev_whitelist.json` |
| 経済カレンダー | `news_calendar.py` (Forex Factory 取得 + 当日リスクスコア) → `calendar.json` |
| 資産管理計算 | `frontend/src/lib/mm.ts` (最低2R/推奨3R。表示・通知の利確目安) |
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
| [`docs/PA_METHOD.md`](docs/PA_METHOD.md) | PA(ローソク足パターン)手法の設計・運用・EV白 |
| [`backtest/PA_FINDINGS.md`](backtest/PA_FINDINGS.md) | PA パターン別バックテスト結果 |
| [`docs/POSTMORTEM_2W.md`](docs/POSTMORTEM_2W.md) | 2週間デモ分析＋RR2/EVゲート/相関キャップ改善 |
| [`docs/candlestick_patterns_reference.html`](docs/candlestick_patterns_reference.html) | PA の出典 (パターン集 原典) |
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
