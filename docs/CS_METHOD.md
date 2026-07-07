# CS 手法 — Currency Strength (通貨強弱)

## 出自 (エビデンス)

R2 実トレード分析で唯一の明確な勝ち筋だった **「USD順張りのドルストレート」
(14勝4敗 +909)** を一般化・コード化した手法。60日バックテストでも同じ構造が
再現: USD/CAD PF8.23 (+7.4R)・USD/CHF +3.3R・NZD/USD PF1.92 は +EV、
**クロス円は全滅 (-22.6R)**。

## ロジック (`strategy_cs.py::analyze_pair_cs`)

```
1. 通貨強弱: 全監視ペアの日足から 8 通貨の強弱スコアを算出
   (0.7×20日 + 0.3×5日 モメンタム、base +/quote − でペア横断平均)
2. 対象: base が上位2位以内 かつ quote が下位2位以内 → long
         (逆なら short)。「最強 vs 最弱」の組合せのみ
3. 日足+4H の analyze_timeframe が同方向 (トレンド一致フィルタ)
4. 15M トリガー: S ランク、または A ランク+重要節目 (MTF と同じ)
5. SL = パターン構造 (1R) / TP = 3R。api 側で最低2R床
```

通貨強弱の計算はペア横断の日足が必要なため `ctx_daily={pair: df}` を受け取る
(api は全ペア分、backtest は `ctx_long` の時点スライス)。

## EVゲート: ドルストレート床

`ev_whitelist._CS_DEFAULT_PAIRS = {USD/CAD, USD/CHF, NZD/USD, EUR/USD, USD/JPY}`

- 根拠: Live(14勝4敗) と backtest(+EV) が収束した実証サブセット。
- **GBP/USD 除外**: Live 0勝3敗 + GBPの無規律さ。
- **AUD/USD 除外**: backtest -EV (n5)。
- **クロス円は全ブロック**: backtest 全滅。whitelist で +EV 実証されれば個別解禁。

## 検証結果 (60日, 2R床) — 2026-07

| ペア | n | WR | PF | 合計R |
|---|--:|--:|--:|--:|
| USD/CAD | 4 | 75% | 8.23 | **+7.4** |
| USD/CHF | 1 | 100% | ∞ | +3.3 |
| NZD/USD | 2 | 50% | 1.92 | +0.9 |
| クロス円 6ペア | 27 | ~10% | <0.6 | **-22.6** |

集計は -14.8R だが内訳が完全に二極化 → ドルストレート床で運用。

## 運用

- MT5: `UseCS=true` (is_alert 準拠なので床が自動適用)。
- 再計測: `python3 scripts/backtest.py --method cs --period 60d --min-rr 2 --emit-whitelist`
- 手動: アラートの「通貨強弱」行でランキングを確認し、最強×最弱の順張りのみ。
