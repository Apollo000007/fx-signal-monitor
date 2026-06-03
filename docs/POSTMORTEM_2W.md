# 2週間 MT5 デモ ポストモーテム & 改善 (2026-06)

## 結果サマリ

14クローズ／実質トントン（クローズ済 約+3、含み-15、スプレッド負け）。
**失敗ではなく「設計上の天井がトントンだった」**。差し値・損切りは手動執行。

## 実トレード集計（ユーザー提供データ）

- 勝7回 平均 **+60** / 負7回 平均 **-60** → 実効RR ≈ **1.0**、勝率 **50%**。
- 最大損 -110, -94, -86 が最大益 +98, +88, +64 より大 = **負けを伸ばし勝ちを刈る**。
- **GBP/USD ショート3連敗 -231**（逆張り・同一通貨の重ね打ち）。
- JPYクロスのロング（chfjpy/nzdjpy/eurjpy/usdjpy）はほぼ全勝。

## 根本原因（コード調査で確定）

1. **RR ≈ 1:1**: 旧 PDHL TP = `entry ± 1R`。勝率50%×1:1 は数学的にスプレッド負け。
2. **2R化が表示だけ**: `_mm_levels`/`mm.ts` は Telegram/UI 表示のみ。signals.json /
   paper / MT5 の**実値は 1:1 のまま漏れていた**。
3. **DTP に ペア制限なし**: +EV は4ペアのみなのに 15ペア全部にアラート。
   実際 EUR/USD・GBP/USD・CHF/JPY 等の非推奨ペアDTPで負けた。
4. **相関キャップなし**: 同一通貨の重ね打ちを抑制していなかった。
5. **致命的運用ミス**: 2R化・PA・DTP改善・カレンダーが**全て未コミット**で、
   本番 Vercel は旧1:1ロジックのまま2週間戦っていた。

## 実施した改善（このセッション）

| 改善 | 内容 | ファイル |
|---|---|---|
| **TP 最低2R床** | 全シグナルの TP を `max(構造TP, 2R)` に。signals.json/Telegram/paper/MT5 の実値まで反映。1:1 を廃止 | `risk.py`, `api.py::_signal_to_dict` |
| **手法×ペア EVゲート** | +EV 実証 (method,pair) のみ `is_alert`。TRIPLE=常時許可(合議が EVゲート)、DTP=証拠4ペア∪whitelist、PDHL/ORZ=降格 | `ev_whitelist.py`, `api.py`, `scripts/backtest.py --emit-whitelist` |
| **通知を+EVに集中** | Telegram は triple/dtp/pa のみ。PDHL/ORZ は UI「参考」表示に降格 | `build_static.METHODS_TO_NOTIFY`, `MethodTabs.tsx` |
| **相関＋同時数キャップ** | 1サイクル最大4件、同一通貨は最大1件 | `build_static.detect_new_alerts` |
| **backtest=本番一致** | バックテストにも2R床 (`--min-rr 2`)。`--emit-whitelist` で `state/ev_whitelist.json` 生成 | `backtest/engine.py`, `scripts/backtest.py` |

### 60日バックテスト（2R床）の手法別 +EV

| 手法 | 件数 | 勝率 | PF | EV(R) | 判定 |
|---|--:|--:|--:|--:|---|
| TRIPLE | 8 | 62.5% | 3.03 | +0.833 | ★ 明確 +EV（低頻度・高精度） |
| PA | 13 | 30.8% | 1.00 | +0.00 | ほぼトントン（白で厳選） |
| DTP | 261 | 23.4% | 0.80 | -0.159 | 集計-EVだが4ペアは+EV |
| PDHL | 200 | 30.5% | 0.80 | -0.141 | -EV → 降格 |
| ORZ | 54 | 20.4% | 0.40 | -0.462 | -EV → 降格 |

DTP +EVペア（2R床・60d）: AUD/JPY +7.7R / NZD/USD +3.8R / GBP/JPY +5.3R /
USD/CHF +1.7R（＝先行研究の4ペアと一致）。

## 今後の運用ルール（手動執行の指針）

1. **利確は最低2R**。表示の「利確 最低2R／推奨3R」に従う。1:1 で利食わない。
2. **損小利大の仕組み化**: 1Rで半分利確 → SLを建値へ → 残りを3Rへ伸ばす。
3. **アラートが出た手法・ペアだけ触る**（TRIPLE / DTP4ペア / PA白）。
   PDHL・ORZ タブは参考。EUR/USD等のDTPは**もう出ない**。
4. **同一通貨の重ね打ち禁止**（GBP/USD3連敗の再発防止）。
5. **逆張り禁止**。上位足トレンドと同方向のみ。
6. **記録継続**: 14トレードは統計的に無意味。最低100トレードで判断。
   各トレードでルール遵守度（順方向／節目／RR2／部分利確）を S〜D で自己採点。

## 次にやること

1. 本改善を**コミット＆Vercelへデプロイ**（最重要。本番反映で初めて効く）。
2. MT5 EA は `MaxPositions` で相関上限、`UseTP3R=true` 推奨。signals.json の
   補正TP（≥2R）を自動で読む。
3. 次の2週間デモを新ロジックで実施 → 規律スコアと損益を持参して再分析。
4. 定期的に `python3 scripts/backtest.py --emit-whitelist --period 60d --min-rr 2`
   を再実行し `ev_whitelist.json` を更新（相場構造の変化に追従）。
