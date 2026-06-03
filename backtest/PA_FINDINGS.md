# PA (ローソク足パターン) バックテスト結果

- 生成: 2026-05-18T00:35:07.926682+00:00
- 期間: 60d / sample_step=2 / threshold=75
- 採用条件: n≥20 かつ PF≥1.1 かつ EV>0
- **採用 (ホワイトリスト登録): 1 組合せ**

## パターン別 集計 (全ペア合算)

| パターン | ランク | trades | WR% | PF | EV(R) | totalR |
|---|---|--:|--:|--:|--:|--:|
| 明けの明星 (morning_star) | S | 2 | 50.0 | 2.60 | +0.815 | +1.6 |
| はらみ寄せ線(強気) (harami_cross_bull) | A | 10 | 50.0 | 1.26 | +0.138 | +1.4 |
| 陰の包み足 (engulf_bear) | S | 53 | 34.0 | 1.13 | +0.091 | +4.8 |
| ピンバー(陽) (pin_bar_bull) | S | 183 | 35.0 | 1.13 | +0.089 | +16.3 |
| 陽の包み足 (engulf_bull) | S | 121 | 30.6 | 0.90 | -0.073 | -8.8 |
| 切り込み線 (piercing_line) | A | 7 | 28.6 | 0.84 | -0.118 | -0.8 |
| 赤三兵 (three_white_soldiers) | A | 4 | 25.0 | 0.83 | -0.129 | -0.5 |
| ピンバー(陰) (pin_bar_bear) | S | 101 | 30.7 | 0.80 | -0.150 | -15.2 |
| かぶせ線 (dark_cloud_cover) | A | 4 | 25.0 | 0.64 | -0.282 | -1.1 |
| 毛抜き底 (tweezer_bottom) | A | 37 | 24.3 | 0.49 | -0.422 | -15.6 |
| 毛抜き天井 (tweezer_top) | A | 12 | 16.7 | 0.40 | -0.561 | -6.7 |
| 宵の明星 (evening_star) | S | 1 | 0.0 | 0.00 | -1.010 | -1.0 |
| 黒三兵(三羽烏) (three_black_crows) | A | 5 | 0.0 | 0.00 | -1.018 | -5.1 |
| はらみ寄せ線(弱気) (harami_cross_bear) | A | 6 | 0.0 | 0.00 | -1.052 | -6.3 |
| ハンマー(カラカサ) (hammer) | A | 1 | 0.0 | 0.00 | -1.065 | -1.1 |
| 流れ星(流星) (shooting_star) | A | 1 | 0.0 | 0.00 | -1.308 | -1.3 |

## ペア×パターン 採用判定

| ペア | パターン | ランク | trades | WR% | PF | EV(R) | 採用 |
|---|---|---|--:|--:|--:|--:|:--:|
| CAD/JPY | ピンバー(陽) (pin_bar_bull) | S | 24 | 45.8 | 1.93 | +0.525 | ✅ |
| AUD/JPY | 陽の包み足 (engulf_bull) | S | 18 | 33.3 | 1.16 | +0.111 | — |
| AUD/JPY | ピンバー(陽) (pin_bar_bull) | S | 23 | 34.8 | 1.01 | +0.007 | — |
| AUD/JPY | 毛抜き底 (tweezer_bottom) | A | 7 | 14.3 | 0.21 | -0.709 | — |
| AUD/USD | かぶせ線 (dark_cloud_cover) | A | 1 | 0.0 | 0.00 | -1.043 | — |
| AUD/USD | 陰の包み足 (engulf_bear) | S | 3 | 33.3 | 0.72 | -0.196 | — |
| AUD/USD | 陽の包み足 (engulf_bull) | S | 10 | 40.0 | 0.98 | -0.011 | — |
| AUD/USD | はらみ寄せ線(強気) (harami_cross_bull) | A | 1 | 100.0 | ∞ | +1.783 | — |
| AUD/USD | 切り込み線 (piercing_line) | A | 4 | 0.0 | 0.00 | -1.038 | — |
| AUD/USD | ピンバー(陰) (pin_bar_bear) | S | 3 | 0.0 | 0.00 | -1.039 | — |
| AUD/USD | ピンバー(陽) (pin_bar_bull) | S | 19 | 26.3 | 0.64 | -0.276 | — |
| AUD/USD | 赤三兵 (three_white_soldiers) | A | 3 | 33.3 | 1.25 | +0.173 | — |
| AUD/USD | 毛抜き底 (tweezer_bottom) | A | 6 | 16.7 | 0.42 | -0.497 | — |
| CAD/JPY | 陰の包み足 (engulf_bear) | S | 2 | 0.0 | 0.00 | -1.056 | — |
| CAD/JPY | 陽の包み足 (engulf_bull) | S | 9 | 33.3 | 0.97 | -0.020 | — |
| CAD/JPY | はらみ寄せ線(弱気) (harami_cross_bear) | A | 1 | 0.0 | 0.00 | -1.058 | — |
| CAD/JPY | はらみ寄せ線(強気) (harami_cross_bull) | A | 1 | 0.0 | 0.00 | -1.066 | — |
| CAD/JPY | ピンバー(陰) (pin_bar_bear) | S | 2 | 0.0 | 0.00 | -1.054 | — |
| CAD/JPY | 毛抜き底 (tweezer_bottom) | A | 3 | 33.3 | 1.15 | +0.103 | — |
| CHF/JPY | 陰の包み足 (engulf_bear) | S | 1 | 0.0 | 0.00 | -1.022 | — |
| CHF/JPY | 陽の包み足 (engulf_bull) | S | 3 | 0.0 | 0.00 | -1.020 | — |
| CHF/JPY | ピンバー(陰) (pin_bar_bear) | S | 4 | 0.0 | 0.00 | -1.029 | — |
| CHF/JPY | ピンバー(陽) (pin_bar_bull) | S | 13 | 53.8 | 2.71 | +0.810 | — |
| EUR/GBP | 陰の包み足 (engulf_bear) | S | 4 | 25.0 | 0.84 | -0.123 | — |
| EUR/GBP | 陽の包み足 (engulf_bull) | S | 3 | 33.3 | 1.34 | +0.239 | — |
| EUR/GBP | ピンバー(陰) (pin_bar_bear) | S | 7 | 28.6 | 0.98 | -0.016 | — |
| EUR/GBP | ピンバー(陽) (pin_bar_bull) | S | 3 | 0.0 | 0.00 | -1.048 | — |
| EUR/GBP | 毛抜き天井 (tweezer_top) | A | 1 | 100.0 | ∞ | +2.388 | — |
| EUR/JPY | 陰の包み足 (engulf_bear) | S | 1 | 0.0 | 0.00 | -1.029 | — |
| EUR/JPY | 陽の包み足 (engulf_bull) | S | 7 | 42.9 | 1.72 | +0.425 | — |
| EUR/JPY | ピンバー(陽) (pin_bar_bull) | S | 10 | 30.0 | 1.05 | +0.039 | — |
| EUR/JPY | 毛抜き底 (tweezer_bottom) | A | 3 | 0.0 | 0.00 | -1.031 | — |
| EUR/JPY | 毛抜き天井 (tweezer_top) | A | 1 | 0.0 | 0.00 | -1.034 | — |
| EUR/USD | かぶせ線 (dark_cloud_cover) | A | 1 | 0.0 | 0.00 | -1.020 | — |
| EUR/USD | 陰の包み足 (engulf_bear) | S | 5 | 40.0 | 2.01 | +0.614 | — |
| EUR/USD | 陽の包み足 (engulf_bull) | S | 2 | 100.0 | ∞ | +2.075 | — |
| EUR/USD | はらみ寄せ線(強気) (harami_cross_bull) | A | 2 | 50.0 | 2.00 | +0.514 | — |
| EUR/USD | ピンバー(陰) (pin_bar_bear) | S | 8 | 50.0 | 2.43 | +0.734 | — |
| EUR/USD | ピンバー(陽) (pin_bar_bull) | S | 7 | 28.6 | 0.95 | -0.036 | — |
| EUR/USD | 黒三兵(三羽烏) (three_black_crows) | A | 2 | 0.0 | 0.00 | -1.015 | — |
| EUR/USD | 毛抜き底 (tweezer_bottom) | A | 1 | 0.0 | 0.00 | -1.030 | — |
| EUR/USD | 毛抜き天井 (tweezer_top) | A | 1 | 0.0 | 0.00 | -1.029 | — |
| GBP/JPY | 陰の包み足 (engulf_bear) | S | 1 | 0.0 | 0.00 | -1.031 | — |
| GBP/JPY | 陽の包み足 (engulf_bull) | S | 10 | 40.0 | 1.59 | +0.362 | — |
| GBP/JPY | ピンバー(陰) (pin_bar_bear) | S | 1 | 0.0 | 0.00 | -1.023 | — |
| GBP/JPY | ピンバー(陽) (pin_bar_bull) | S | 8 | 25.0 | 0.75 | -0.193 | — |
| GBP/JPY | 毛抜き底 (tweezer_bottom) | A | 2 | 50.0 | 1.73 | +0.378 | — |
| GBP/USD | かぶせ線 (dark_cloud_cover) | A | 1 | 100.0 | ∞ | +1.966 | — |
| GBP/USD | 陰の包み足 (engulf_bear) | S | 7 | 28.6 | 0.70 | -0.215 | — |
| GBP/USD | 陽の包み足 (engulf_bull) | S | 7 | 14.3 | 0.37 | -0.550 | — |
| GBP/USD | 宵の明星 (evening_star) | S | 1 | 0.0 | 0.00 | -1.010 | — |
| GBP/USD | はらみ寄せ線(弱気) (harami_cross_bear) | A | 1 | 0.0 | 0.00 | -1.027 | — |
| GBP/USD | はらみ寄せ線(強気) (harami_cross_bull) | A | 1 | 0.0 | 0.00 | -1.025 | — |
| GBP/USD | 切り込み線 (piercing_line) | A | 1 | 0.0 | 0.00 | -1.017 | — |
| GBP/USD | ピンバー(陰) (pin_bar_bear) | S | 14 | 28.6 | 0.83 | -0.127 | — |
| GBP/USD | ピンバー(陽) (pin_bar_bull) | S | 11 | 36.4 | 1.35 | +0.232 | — |
| GBP/USD | 黒三兵(三羽烏) (three_black_crows) | A | 1 | 0.0 | 0.00 | -1.010 | — |
| GBP/USD | 毛抜き底 (tweezer_bottom) | A | 3 | 33.3 | 0.37 | -0.431 | — |
| GBP/USD | 毛抜き天井 (tweezer_top) | A | 1 | 0.0 | 0.00 | -1.019 | — |
| NZD/JPY | 陰の包み足 (engulf_bear) | S | 5 | 20.0 | 0.48 | -0.441 | — |
| NZD/JPY | 陽の包み足 (engulf_bull) | S | 13 | 38.5 | 1.16 | +0.100 | — |
| NZD/JPY | ハンマー(カラカサ) (hammer) | A | 1 | 0.0 | 0.00 | -1.065 | — |
| NZD/JPY | はらみ寄せ線(弱気) (harami_cross_bear) | A | 1 | 0.0 | 0.00 | -1.051 | — |
| NZD/JPY | ピンバー(陰) (pin_bar_bear) | S | 8 | 37.5 | 1.14 | +0.091 | — |
| NZD/JPY | ピンバー(陽) (pin_bar_bull) | S | 10 | 20.0 | 0.57 | -0.366 | — |
| NZD/USD | かぶせ線 (dark_cloud_cover) | A | 1 | 0.0 | 0.00 | -1.031 | — |
| NZD/USD | 陰の包み足 (engulf_bear) | S | 7 | 71.4 | 5.58 | +1.340 | — |
| NZD/USD | 陽の包み足 (engulf_bull) | S | 4 | 50.0 | 2.07 | +0.561 | — |
| NZD/USD | はらみ寄せ線(弱気) (harami_cross_bear) | A | 1 | 0.0 | 0.00 | -1.073 | — |
| NZD/USD | はらみ寄せ線(強気) (harami_cross_bull) | A | 3 | 33.3 | 0.04 | -0.706 | — |
| NZD/USD | 切り込み線 (piercing_line) | A | 1 | 100.0 | ∞ | +2.492 | — |
| NZD/USD | ピンバー(陰) (pin_bar_bear) | S | 16 | 43.8 | 1.33 | +0.199 | — |
| NZD/USD | ピンバー(陽) (pin_bar_bull) | S | 10 | 50.0 | 1.50 | +0.267 | — |
| NZD/USD | 黒三兵(三羽烏) (three_black_crows) | A | 2 | 0.0 | 0.00 | -1.026 | — |
| NZD/USD | 赤三兵 (three_white_soldiers) | A | 1 | 0.0 | 0.00 | -1.036 | — |
| NZD/USD | 毛抜き底 (tweezer_bottom) | A | 2 | 0.0 | 0.00 | -1.053 | — |
| NZD/USD | 毛抜き天井 (tweezer_top) | A | 1 | 100.0 | ∞ | +2.041 | — |
| USD/CAD | 陰の包み足 (engulf_bear) | S | 8 | 25.0 | 0.86 | -0.104 | — |
| USD/CAD | 陽の包み足 (engulf_bull) | S | 3 | 33.3 | 1.12 | +0.084 | — |
| USD/CAD | はらみ寄せ線(弱気) (harami_cross_bear) | A | 1 | 0.0 | 0.00 | -1.036 | — |
| USD/CAD | ピンバー(陰) (pin_bar_bear) | S | 4 | 0.0 | 0.00 | -1.029 | — |
| USD/CAD | ピンバー(陽) (pin_bar_bull) | S | 13 | 30.8 | 0.98 | -0.016 | — |
| USD/CAD | 毛抜き天井 (tweezer_top) | A | 1 | 0.0 | 0.00 | -1.025 | — |
| USD/CHF | 陰の包み足 (engulf_bear) | S | 7 | 57.1 | 2.73 | +0.779 | — |
| USD/CHF | 陽の包み足 (engulf_bull) | S | 8 | 12.5 | 0.32 | -0.615 | — |
| USD/CHF | はらみ寄せ線(弱気) (harami_cross_bear) | A | 1 | 0.0 | 0.00 | -1.066 | — |
| USD/CHF | 明けの明星 (morning_star) | S | 1 | 0.0 | 0.00 | -1.017 | — |
| USD/CHF | ピンバー(陰) (pin_bar_bear) | S | 9 | 22.2 | 0.69 | -0.252 | — |
| USD/CHF | ピンバー(陽) (pin_bar_bull) | S | 15 | 40.0 | 1.51 | +0.318 | — |
| USD/CHF | 毛抜き底 (tweezer_bottom) | A | 3 | 66.7 | 4.38 | +1.185 | — |
| USD/CHF | 毛抜き天井 (tweezer_top) | A | 1 | 0.0 | 0.00 | -1.039 | — |
| USD/JPY | 陰の包み足 (engulf_bear) | S | 1 | 0.0 | 0.00 | -1.034 | — |
| USD/JPY | 陽の包み足 (engulf_bull) | S | 15 | 20.0 | 0.65 | -0.288 | — |
| USD/JPY | はらみ寄せ線(強気) (harami_cross_bull) | A | 1 | 100.0 | ∞ | +1.422 | — |
| USD/JPY | 明けの明星 (morning_star) | S | 1 | 100.0 | ∞ | +2.648 | — |
| USD/JPY | ピンバー(陰) (pin_bar_bear) | S | 2 | 0.0 | 0.00 | -1.047 | — |
| USD/JPY | ピンバー(陽) (pin_bar_bull) | S | 16 | 31.2 | 0.84 | -0.115 | — |
| USD/JPY | 毛抜き底 (tweezer_bottom) | A | 2 | 50.0 | 0.48 | -0.271 | — |
| ZAR/JPY | 陰の包み足 (engulf_bear) | S | 1 | 0.0 | 0.00 | -1.202 | — |
| ZAR/JPY | 陽の包み足 (engulf_bull) | S | 9 | 11.1 | 0.15 | -1.073 | — |
| ZAR/JPY | はらみ寄せ線(強気) (harami_cross_bull) | A | 1 | 100.0 | ∞ | +1.356 | — |
| ZAR/JPY | 切り込み線 (piercing_line) | A | 1 | 100.0 | ∞ | +1.853 | — |
| ZAR/JPY | ピンバー(陰) (pin_bar_bear) | S | 23 | 39.1 | 0.76 | -0.184 | — |
| ZAR/JPY | ピンバー(陽) (pin_bar_bull) | S | 1 | 0.0 | 0.00 | -1.482 | — |
| ZAR/JPY | 流れ星(流星) (shooting_star) | A | 1 | 0.0 | 0.00 | -1.308 | — |
| ZAR/JPY | 毛抜き底 (tweezer_bottom) | A | 5 | 20.0 | 0.27 | -0.846 | — |
| ZAR/JPY | 毛抜き天井 (tweezer_top) | A | 5 | 0.0 | 0.00 | -1.203 | — |

## 解釈・運用

- ✅ の組合せのみ `state/pa_whitelist.json` に登録され、本番 PA アラートの対象になる（厳格運用）。
- ホワイトリスト未生成/不在時は **S ランクのみ暫定許可**（誤爆抑制）。
- サンプル < 20 は統計的に無意味 → 採用しない（過剰最適化回避）。
- 定期再実行で陳腐化を防ぐ（相場構造は変化する）。
- 注意: バックテストの優位性が Live で再現する保証はない。ペーパートレード/デモで二重確認すること。
