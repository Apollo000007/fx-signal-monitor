# MTF 手法 — Multi-TimeFrame 全軸トレンド一致 + 15Mパターン

## 目的

**週足・日足・4時間足・1時間足が全て同じトレンド方向**（全部買い相場 or
全部売り相場）に揃ったときだけ、**15分足でその方向のチャート/ローソク足
パターン(S/Aランク)**が出たらエントリーする順張り手法。

PA手法（D1+4H 一致 + 15Mパターン）の上位版。整合する時間軸を4軸に強化した
「全軸一致」高確度セットアップ。**低頻度・高精度**。

## ロジック (`strategy_mtf.py::analyze_pair_mtf`)

```
1. トレンド判定 (各TF): strategy.analyze_timeframe(df).direction
     "up"→買い / "down"→売り / "range"→不明
   - 週足 = 日足 df を resample("1W") して生成 (新規fetch不要・backtest互換)
   - 日足 = LONG (1d, 3y)、4H = MID (1h→4h)、1H = H1 (1h)
   - 全4軸が買い → long、全4軸が売り → short。1つでも range/不一致なら見送り
2. 15Mトリガー: patterns.detect(確定足) から
     sig == aligned方向 かつ rank ∈ {S, A} のパターンを採用 (rank→strength で最良)
3. SL = パターン構造(sl_hint)±バッファ = 1R / TP = 3R
   → api 側 risk.min_rr_tp が最低2R床を保証 (1:1 を作らない)
4. score = 50 (4軸一致) + ランク基礎(S:55/A:45) + strength
   is_alert = 4軸一致 and S/Aトリガー and score≥75 and SL/TP整合
```

確定足のみ評価（進行中の15Mバーは使わない）。`analyze_timeframe` は
ダウ理論+SMA配列+一目雲+傾きで方向を判定するため、明確なトレンドのみ "up/down"
になり、レンジ相場は自動的に除外される。

## EVゲート / 通知

- `ev_whitelist.is_pair_allowed("mtf", pair)` = **常時許可**（TRIPLE 同様）。
  4軸一致＋S/Aパターン＋2R という内在ゲートが強いため、ペア別 whitelist は課さない。
- `METHODS_TO_NOTIFY` 優先度: triple > **mtf** > dtp > pa。
- 相関キャップ（1サイクル最大4件・同一通貨1件）は全手法共通で適用。

## バックテスト

```bash
python3 scripts/backtest.py --method mtf --period 60d --min-rr 2
```

(初回 60日検証の結果は本ファイル末尾「検証結果」に追記する。-EV なら
S/A→S限定や節目条件追加で絞る方針。)

## 運用メモ

- 全軸一致は滅多に揃わない＝アラート頻度は低い。出たら高確度の順張り。
- MT5: `UseMTF=true`。`is_alert` 準拠なので signals.json の補正TP(≥2R)を自動追従。
- 手動: 4軸が同方向で揃い、15MでS/Aパターン → その方向にエントリー、SL=パターン
  構造、利確は最低2R/推奨3R（1Rで半分利確→建値移動→残り3R）。

## 検証結果 (60日, 2R床)

<!-- scripts/backtest.py --method mtf --period 60d --min-rr 2 の結果を追記 -->
（バックテスト実行後に追記）
