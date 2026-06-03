# PA 手法 — ローソク足／チャートパターン (Price Action)

出典: `docs/candlestick_patterns_reference.html`
（「ロウソク足パターン集 — 15分足トレード実践（信頼度ランク付き）」）

## 目的

参照 HTML のパターンが出たらアラートを鳴らす。ただし **パターン単体は
機能しにくい** ため、HTML が説く「大前提」をハードゲート化し、さらに
**実データで +EV と確認できた pair×pattern だけ** をアラート対象にする。

## アーキテクチャ

```
patterns.py            純 OHLC パターン検出器 (Phase 1: 単体/2本/3本組 ~32種)
  └ PATTERN_META       各パターンの rank(S/A/B/C)/sig/解説 (HTML 由来)
strategy_pa.py         analyze_pair_pa() — 大前提ハードゲート + スコア化
  ├ ② 上位足順方向     日足+4H 50EMA バイアスと同方向のみ
  ├ ③ 重要節目         PDH/PDL・スイングS/R・SMA20/50・キリ番 に重なる時のみ
  ├ ① 確定足           評価足=iloc[-2] / 確認足=iloc[-1] (進行中足で判断しない)
  ├ ④ 次足確認         確認足がシグナル方向に確定して成立
  ├ ランクゲート       S/A のみ has_trigger (B=内部点 / C=文脈)
  ├ ⑤ 資金管理         SL=パターン構造(1R) / TP=固定3R
  ├ 指標リスク抑制     state/calendar_cache.json: 当日★4+ / 対象通貨High近接で抑制
  └ EV ホワイトリスト  state/pa_whitelist.json の pair×pattern のみ is_alert
api.py / build_static.py / backtest/engine.py / paper_trade/runner.py
  既存 dtp と同じ統合点に "pa" を追加。frontend は手法タブ「PA」(ショートカット 7)。
```

## 勝率を高める核心: EV ホワイトリスト

`scripts/backtest_pa.py` が全ペア×全パターンを過去データで個別検証し、
`n≥20 かつ PF≥1.1 かつ EV>0` を満たす組合せだけ `state/pa_whitelist.json`
に登録する。`analyze_pair_pa` はこの組合せだけ `is_alert=True`。

- ホワイトリスト不在/未生成 → **S ランクのみ暫定許可**（誤爆抑制ブートストラップ）。
- 発見モード: `PA_BACKTEST_DISCOVERY=1` で whitelist/指標抑制を外し純 EV を測定
  （`scripts/backtest_pa.py` が自動設定。whitelist の循環依存を回避）。

### 再生成コマンド

```bash
python3 scripts/backtest_pa.py --period 60d            # 全ペア
python3 scripts/backtest_pa.py --pair CAD/JPY -v       # 単一ペア確認
# → state/pa_whitelist.json / backtest/PA_FINDINGS.md
```

定期的に再実行して陳腐化を防ぐ（相場構造は変化する）。最低サンプル 20 で
過剰最適化を回避。バックテストの優位性が Live で再現する保証はない
（ペーパートレード/デモで二重確認）。

## 直近バックテスト所見 (60日, 参考)

- パターン別 +EV: **pin_bar_bull**(S, 183件 PF1.13 +16.3R)、
  **engulf_bear**(S, PF1.13)、**harami_cross_bull**(A, PF1.26)。
- pin_bar_bear / engulf_bull / tweezers は集計 -EV。
- 厳格ゲート採用: `CAD/JPY|pin_bar_bull` (n24 WR45.8% **PF1.93 EV+0.525R**)。
- → ペア依存が大きい（DTP と同じ教訓）。strict + whitelist で運用。

## Phase 2 (未実装・予定)

チャートパターン（ダブルトップ/ボトム・H&S/逆H&S・三角・レンジ・ダウ転換）。
`indicators.find_swings`/`cluster_levels`/既存 Dow 構造を再利用し、
バックテスト検証後に whitelist 経由で有効化する。
