# セッション引き継ぎサマリ (2026-05-15 更新)

次の AI / 自分が続きから作業するための圧縮メモ。

> **まず `../CLAUDE.md` (リポジトリ直下) を読むこと。** あちらが索引兼絶対
> ルール集で、Claude Code は自動ロードする。本ファイルは詳細ダンプ。

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
(`refactor: remove claude/both as user-facing methods (TRIPLE logic intact)`)
→ その後 `docs: session handoff summary` → 本コミットで CLAUDE.md 追加。
Vercel 自動デプロイ済み。push 前は必ず `git pull --rebase origin main`。

---

## 触ってはいけない箇所 (Immutable / 不変条件)

- **【2026-05-18 更新】TRIPLE の SL/TP は変更可。** ユーザーが「トリプルの
  ロジックも損切り/利確ラインを変更して構わない」と明示。当初の「TRIPLE
  全面変更禁止」は SL/TP に関しては解除。`api.py::_build_triple_method` の
  SL/TP 算出は資産管理方針 (最低2R/推奨3R) に寄せてよい。ただし合議の
  方向一致条件など中核ロジックは合意なく変えない。
- `strategy_claude.py::analyze_pair_claude` — TRIPLE が内部で呼ぶ。削除禁止。
  挙動変更時は backtest/paper への影響を必ず確認。
- `api.py::_compute_signals` の `analyze_pair_claude` 呼び出し — 維持必須。
- `~/Downloads/fx-signal-monitor-main` — 古い zip。読み書き禁止。作業は
  `~/dev/fx-signal-monitor` のみ。
- 手法配列の magic / index 対応 (`mt5/Experts/FXSignalEA/FXSignalEA.mq5`) —
  `claude`/`both` の枠は `false` で残してありインデックスを崩さない。

## 直近の意思決定ログ (Decision Log)

- **なぜ claude/both を UI/通知から外したか**: ユーザー要望。ただし TRIPLE は
  ORZ+PDHL+Claude の合議で成り立つため、`claude` の計算自体は API 内部で継続。
  「ユーザーに見せる手法」と「内部部品」を分離した、という整理。
- **なぜ DTP を追加したか**: ORZ/PDHL/TRIPLE が backtest で TRIPLE 以外 -EV。
  再現性ある +EV を狙い、日足トレンド+押し目の DTP を 6 番目として実装。
- **なぜ DTP をホワイトリスト運用にするか**: 全ペア集計は -EV だが
  AUDJPY/NZDUSD/USDCHF/GBPJPY の 4 ペアだけで +32.7R。ZAR/JPY 等が集計を破壊。
  → ペア選択が手法選択より重要、という結論。
- **なぜライブ価格を諦めたか**: Finnhub 403 / Yahoo は Vercel IP block /
  OANDA・Saxo は本人確認でユーザー離脱。5分 cron で運用する判断。
- **なぜ CLAUDE.md 形式か (Skills でなく)**: Claude Code が
  セッション開始時に自動ロードする標準。Skills は on-demand 手順呼び出し用で
  永続文脈には不適。CLAUDE.md(索引) + 本ファイル(詳細) の二層構成を採用。
- **【2026-05-18】利確を最低2R/推奨3R に変更**: チャート/カード/ドロワー/
  Telegram 本文の利確目安が約1:1だったため、`frontend/src/lib/mm.ts` を新設し
  「SL=構造(1R) 固定・利確=Rの倍数(最低2R, 推奨3R, 構造TPが2Rより遠ければ
  採用)」へ統一。`scripts/build_static.py::_mm_levels`/`_format_alert` も同様。
  strategy/api のシグナル本体は当初未変更だったが、上記ルール2の許可により
  TRIPLE 含め本体側も2R/3Rへ寄せてよい (未実施なら次タスク候補)。
- **【2026-06-03】2週間デモ ポストモーテム → +EV化リファクタ**: 実トレード14件が
  RR≈1:1 / 勝率50% で実質トントンだった反省から:
  (1) **TP最低2R床** `risk.min_rr_tp` を `api._signal_to_dict` に適用し signals.json/
  Telegram/paper/MT5 の**実値**まで≥2R化（旧PDHL 1:1 を廃止。表示だけだった2Rを実体化）。
  (2) **手法×ペア EVゲート** `ev_whitelist.is_pair_allowed` を is_alert に適用。
  TRIPLE=常時許可（合議がEVゲート・低頻度高精度）、DTP=証拠4ペア∪whitelist、
  PDHL/ORZ=降格（whitelistのみ＝実質閉）。`scripts/backtest.py --emit-whitelist
  --min-rr 2` で `state/ev_whitelist.json` 生成。
  (3) **通知集中** `METHODS_TO_NOTIFY=(triple,dtp,pa)`、PDHL/ORZ は UI「参考」バッジ。
  (4) **相関キャップ** `detect_new_alerts` に 1サイクル最大4件・同一通貨最大1件。
  (5) backtest にも2R床（`run_backtest(min_rr=2.0)`）で backtest=本番一致。
  60d検証: TRIPLE PF3.03 +0.83R（★）/ PA ±0 / DTP・PDHL・ORZ 集計-EV。
  **重要教訓**: これら改善は長く未コミット＝本番Vercelは旧1:1で稼働していた。
  必ずコミット&デプロイすること。詳細 `docs/POSTMORTEM_2W.md`。
- **【2026-05-18】PA (ローソク足パターン) 手法を追加**: 参照 HTML
  (`docs/candlestick_patterns_reference.html`) 準拠。`patterns.py` (純OHLC検出
  ~32種) + `strategy_pa.py` (大前提ハードゲート: 確定足/上位足順方向/重要節目/
  次足確認/ランクS-A/指標リスク抑制/資金管理3R)。勝率の核心は
  `scripts/backtest_pa.py` が pair×pattern を個別検証し n≥20&PF≥1.1&EV>0 の
  組合せだけ `state/pa_whitelist.json` に登録→そこだけ is_alert。未生成時は
  S ランクのみ暫定許可。dtp と同じ統合点で api/build_static/backtest/paper/
  frontend(タブ「PA」, ショートカット7)に配線。60日検証で
  `CAD/JPY|pin_bar_bull` が PF1.93 EV+0.525R で採用。Phase2=チャートパターン
  (ダブルトップ/H&S/三角) は未実装。詳細 `docs/PA_METHOD.md`。
- **【2026-05-18】経済カレンダー + 当日リスクスコア追加**: `news_calendar.py`
  が Forex Factory 無料フィードを cron で取得し `calendar.json` を出力。
  フロントは `lib/calendar.ts`/`RiskBadge`/`EconCalendarDrawer` で表示
  (ヘッダー星バッジ + 全画面ドロワー, ショートカット N)。リスクは監視全
  通貨の当日 高/中 重要度を加重し星1〜5。Forex Factory はキー不要・GitHub
  Actions のクリーン IP で取得可 (Vercel IP ブロック問題と無関係)。

## 新セッション / 他 AI への引き継ぎ手順

- **新しい Claude Code セッション**: `~/dev/fx-signal-monitor` で起動すれば
  `CLAUDE.md` が自動ロードされる。追加操作不要。本ファイルも続けて読む。
- **他 AI (ChatGPT / Gemini / Cursor 等)**: 以下をそのまま貼って指示する。
  > 「リポジトリ直下の `CLAUDE.md` と `docs/SESSION_HANDOFF.md` を全文読んで
  >  から作業して。特に『絶対ルール』と『触ってはいけない箇所』を厳守。
  >  TRIPLE のロジック (`api.py::_build_triple_method`,
  >  `strategy_claude.py`) は絶対に変更しないこと。」
- **次のステップ**: 2 週間 MT5 Demo (`UseTriple=true`+`UseDTP=true`,
  `TradingPairs=AUDJPY,NZDUSD,USDCHF,GBPJPY`) → 規律スコア (S/A/B/C/D) と
  損益を持参 → backtest と Live の乖離検証 → 戦略取捨選択。
