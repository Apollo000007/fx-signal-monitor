"""ローソク足パターン検出器 (Phase 1: 単体 / 2本組 / 3本組)。

出典: docs/candlestick_patterns_reference.html
  「ロウソク足パターン集 — 15分足トレード実践（信頼度ランク付き）」

設計:
  - 純 OHLC 関数。指標やトレンド判定は含めない (strategy_pa.py が担う)。
  - 各検出器は「渡された DataFrame の最終行を評価対象足」とみなす。
    strategy_pa は確定足を最終行に揃えて呼ぶ (次足確認は strategy 側)。
  - `detect(df)` は最終足にマッチした全パターンを返す。strategy_pa が
    上位足方向・節目・確定・次足確認・ランク・EV ホワイトリストで絞る。

PATTERN_META[key] = {
  name, en, cat, rank(S/A/B/C), sig(long/short/neutral),
  m(意味), e(エントリー), s(損切り), t(利確), fk(ダマシ注意)
}
detect() → [{key, sig, strength(0-1), sl_hint(価格 or None), n_bars}]
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from indicators import find_swings, cluster_levels

RANK_ORDER = {"S": 4, "A": 3, "B": 2, "C": 1}

# ------------------------------------------------------------------ メタ情報
# 本文テキストは reference HTML を要約 (reasons/warnings/docs に使用)。
PATTERN_META: dict[str, dict] = {
    # ---------- 単体 ----------
    "marubozu_bull": dict(name="大陽線(陽の丸坊主)", en="Bullish Marubozu", cat="単体", rank="C", sig="long",
        m="始値から終値までほぼ一直線の強い上昇。買い圧力が圧倒的。", e="安値圏/サポートで押し目買いの起点。単体では追わない。",
        s="この大陽線の安値割れ。", t="直近高値/RR1:2。", fk="高値圏の大陽線は最後の踏み上げのことも。単体では使わない。"),
    "marubozu_bear": dict(name="大陰線(陰の丸坊主)", en="Bearish Marubozu", cat="単体", rank="C", sig="short",
        m="ほぼ一直線の強い下落。売り圧力が圧倒的。", e="高値圏/レジスタンスで戻り売りの起点。",
        s="この大陰線の高値超え。", t="直近安値/RR1:2。", fk="安値圏の大陰線はセリングクライマックスのことも。"),
    "spinning_top": dict(name="コマ", en="Spinning Top", cat="単体", rank="C", sig="neutral",
        m="実体が小さく上下にヒゲ=拮抗・迷い。勢い低下。", e="単体では入らない。トレンド終盤で反転予兆として警戒。",
        s="—", t="—", fk="レンジ中は頻発しノイズ。節目+次足で初めて意味。"),
    "doji": dict(name="十字線(同事)", en="Doji", cat="単体", rank="C", sig="neutral",
        m="始値≒終値。完全な拮抗。転換点になりやすい注意信号。", e="単体不可。天底+重要節目で次足方向に検討。",
        s="十字線のヒゲ外側。", t="直近高安。", fk="レンジ中の十字線は無意味。位置(節目)が全て。"),
    "dragonfly_doji": dict(name="トンボ(下影同事)", en="Dragonfly Doji", cat="単体", rank="B", sig="long",
        m="長い下ヒゲで安値を否定し始値付近に戻る=下げ拒否。底打ち。", e="下落後・サポートで出現→次足陽線で買い。",
        s="トンボの安値の少し下。", t="直近戻り高値/RR1:2。", fk="上位足が強い下降中だと反発は一時的。"),
    "gravestone_doji": dict(name="トウバ/墓石(上影同事)", en="Gravestone Doji", cat="単体", rank="B", sig="short",
        m="長い上ヒゲで高値を否定。天井サイン。", e="上昇後・レジスタンスで出現→次足陰線で売り。",
        s="上ヒゲ先の少し上。", t="直近押し安値/RR1:2。", fk="強い上昇中は一時的。戻り売りの位置で使う。"),
    "hammer": dict(name="ハンマー(カラカサ)", en="Hammer", cat="単体", rank="A", sig="long",
        m="下落の底で長い下ヒゲ+小実体。売られたが買い戻された=強い反発示唆。", e="明確な下落後+サポートで出現→次足陽線確定で買い。",
        s="ハンマーの安値(下ヒゲ先)の下。", t="直近高値/RR1:2。損切り浅く良形。", fk="節目でない所のハンマーは弱い。位置と次足確認必須。"),
    "inverted_hammer": dict(name="逆ハンマー", en="Inverted Hammer", cat="単体", rank="B", sig="long",
        m="下落の底で長い上ヒゲ+小実体。反発初期(要確認)。", e="下落後・サポートで出現。必ず次足の強い陽線を待つ。",
        s="逆ハンマーの安値の下。", t="直近高値/RR1:2。", fk="単体信頼度低め。確認なしは戻り売りに巻き込まれる。"),
    "hanging_man": dict(name="首吊り線", en="Hanging Man", cat="単体", rank="B", sig="short",
        m="形はハンマーと同じだが上昇の天井で出る=下落転換警戒。", e="上昇後・レジスタンスで出現→次足陰線確定で売り。",
        s="首吊り線の高値の上。", t="直近安値/RR1:2。", fk="位置で意味が真逆。上昇継続も多く確認必須。"),
    "shooting_star": dict(name="流れ星(流星)", en="Shooting Star", cat="単体", rank="A", sig="short",
        m="上昇の天井で長い上ヒゲ+小実体。買われたが売り戻された=反落示唆。", e="明確な上昇後+レジスタンスで出現→次足陰線確定で売り。",
        s="流れ星の高値(上ヒゲ先)の上。", t="直近安値/RR1:2。損切り浅い良形。", fk="節目でない所の流れ星は弱い。位置と次足確認必須。"),
    "long_legged_doji": dict(name="足長同事", en="Long-legged Doji", cat="単体", rank="C", sig="neutral",
        m="上下に非常に長いヒゲ+実体ほぼ無=極度の迷い。大転換の前触れになりうる。", e="単体不可。天底+節目で次足方向に従う。",
        s="ヒゲ外側。", t="直近高安。", fk="ボラ急増のノイズも多い。重要指標前後は無視。"),
    "pin_bar_bull": dict(name="ピンバー(陽)", en="Bullish Pin Bar", cat="単体", rank="S", sig="long",
        m="長い下ヒゲで価格を明確に拒絶。海外勢の主力サイン。", e="重要な水平線/前日高安/キリ番でヒゲが水準を否定→上方向にエントリー。",
        s="下ヒゲ先の少し外側(損切り浅くRRを取りやすい)。", t="RR1:2以上/直近高安。", fk="重要な節目で出たもの限定。何もない所の長ヒゲは無視。"),
    "pin_bar_bear": dict(name="ピンバー(陰)", en="Bearish Pin Bar", cat="単体", rank="S", sig="short",
        m="長い上ヒゲで価格を明確に拒絶。海外勢の主力サイン。", e="重要な水平線/前日高安/キリ番でヒゲが水準を否定→下方向にエントリー。",
        s="上ヒゲ先の少し外側。", t="RR1:2以上/直近高安。", fk="重要な節目で出たもの限定。何もない所の長ヒゲは無視。"),
    # ---------- 2本組 ----------
    "engulf_bull": dict(name="陽の包み足", en="Bullish Engulfing", cat="2本組", rank="S", sig="long",
        m="小さな陰線を次の大陽線が完全に包む。買いが売りを飲み込んだ=強力反転。", e="下落後・サポートで2本目大陽線確定で買い。",
        s="2本目大陽線の安値の下。", t="直近高値/RR1:2〜。", fk="レンジ内の包み足は弱い。天底圏+節目で信頼大。"),
    "engulf_bear": dict(name="陰の包み足", en="Bearish Engulfing", cat="2本組", rank="S", sig="short",
        m="小さな陽線を次の大陰線が完全に包む=強力天井反転。", e="上昇後・レジスタンスで2本目大陰線確定で売り。",
        s="2本目大陰線の高値の上。", t="直近安値/RR1:2〜。", fk="強い上昇の押し目では機能しにくい。天井圏+節目で信頼大。"),
    "harami_bull": dict(name="はらみ足(強気)", en="Bullish Harami", cat="2本組", rank="B", sig="long",
        m="大陰線の後その実体に収まる小陽線。下落の勢い減速=反転初期。", e="下落後に出現→次足が陽線で上抜け確定で買い。",
        s="大陰線(1本目)の安値の下。", t="直近戻り高値/RR1:1.5。", fk="包み足より弱い減速サイン。必ず確認。"),
    "harami_bear": dict(name="はらみ足(弱気)", en="Bearish Harami", cat="2本組", rank="B", sig="short",
        m="大陽線の後その実体に収まる小陰線。上昇の勢い減速=反転初期。", e="上昇後に出現→次足が陰線で下抜け確定で売り。",
        s="大陽線(1本目)の高値の上。", t="直近押し安値/RR1:1.5。", fk="包み足より弱い。必ず確認。"),
    "harami_cross_bull": dict(name="はらみ寄せ線(強気)", en="Bullish Harami Cross", cat="2本組", rank="A", sig="long",
        m="大陰線の後に十字線がはらむ。迷いが極まり反転確度が高い(はらみ強化版)。", e="下落後・サポートで出現→次足の陽線確定で買い。",
        s="1本目の安値の下。", t="直近高値/RR1:2。", fk="位置が重要。トレンド途中だと一時停止で終わることも。"),
    "harami_cross_bear": dict(name="はらみ寄せ線(弱気)", en="Bearish Harami Cross", cat="2本組", rank="A", sig="short",
        m="大陽線の後に十字線がはらむ。反転確度が高い。", e="上昇後・レジスタンスで出現→次足の陰線確定で売り。",
        s="1本目の高値の上。", t="直近安値/RR1:2。", fk="位置が重要。トレンド途中だと一時停止で終わることも。"),
    "dark_cloud_cover": dict(name="かぶせ線", en="Dark Cloud Cover", cat="2本組", rank="A", sig="short",
        m="上昇中、大陽線の翌足が上に窓を開け陽線の実体半分以下まで急落。天井反転。", e="上昇後・レジスタンスで2本目が陽線中値割りで確定→売り。",
        s="2本目の高値の上。", t="直近安値/RR1:2。", fk="割込みが浅い(中値未満でない)と不成立。深いほど強い。"),
    "piercing_line": dict(name="切り込み線", en="Piercing Line", cat="2本組", rank="A", sig="long",
        m="下落中、大陰線の翌足が下に窓を開け陰線の実体半分以上まで急反発。底反転。", e="下落後・サポートで2本目が陰線中値超えで確定→買い。",
        s="2本目の安値の下。", t="直近高値/RR1:2。", fk="反発が中値未満だと不成立(弱い)。中値を大きく超えるほど強い。"),
    "tweezer_top": dict(name="毛抜き天井", en="Tweezer Top", cat="2本組", rank="A", sig="short",
        m="2本の高値がほぼ揃う(陽→陰)。同価格で2度跳ね返された=強い抵抗。", e="上昇後・レジスタンスで高値が揃い2本目陰線確定→売り。",
        s="揃った高値のすぐ上(損切り極浅)。", t="直近安値/RR1:2〜3。", fk="水平線と一致で非常に強い。バラついた高値は無効。"),
    "tweezer_bottom": dict(name="毛抜き底", en="Tweezer Bottom", cat="2本組", rank="A", sig="long",
        m="2本の安値がほぼ揃う(陰→陽)。同価格で2度支えられた=強いサポート。", e="下落後・サポートで安値が揃い2本目陽線確定→買い。",
        s="揃った安値のすぐ下(浅い損切り)。", t="直近高値/RR1:2〜3。", fk="水平線と一致で強力。安値がズレれば無効。"),
    "counterattack_bull": dict(name="出会い線(強気)", en="Bullish Counterattack", cat="2本組", rank="B", sig="long",
        m="逆方向の大ロウソクが前足とほぼ同じ終値で止まる=勢いが受け止められた。", e="トレンド終盤+節目で出現→次足方向確認で買い。",
        s="2本のヒゲ外側。", t="直近高安/RR1:1.5。", fk="包み足より弱い。終値が揃っていることが条件。確認必須。"),
    "counterattack_bear": dict(name="出会い線(弱気)", en="Bearish Counterattack", cat="2本組", rank="B", sig="short",
        m="逆方向の大ロウソクが前足とほぼ同じ終値で止まる=勢いが受け止められた。", e="トレンド終盤+節目で出現→次足方向確認で売り。",
        s="2本のヒゲ外側。", t="直近高安/RR1:1.5。", fk="包み足より弱い。終値が揃っていることが条件。確認必須。"),
    "tasuki_up": dict(name="上げたすき線", en="Upside Tasuki Gap", cat="2本組", rank="B", sig="long",
        m="上昇中、陽線の後に窓を埋めない小陰線=押し目(継続)。", e="上昇トレンド中、窓が埋まらず次足陽線→押し目買い(順張り)。",
        s="窓(または2本目の安値)の下。", t="直近高値更新/トレンド終了まで。", fk="窓を完全に埋めたら継続消滅。トレンド明確時のみ。"),
    "tasuki_down": dict(name="下げたすき線", en="Downside Tasuki Gap", cat="2本組", rank="B", sig="short",
        m="下降中、陰線の後に窓を埋めない小陽線=戻り(継続)。", e="下降トレンド中、窓が埋まらず次足陰線→戻り売り(順張り)。",
        s="窓(または2本目の高値)の上。", t="直近安値更新/トレンド終了まで。", fk="窓を完全に埋めたら継続消滅。トレンド明確時のみ。"),
    # ---------- 3本組 ----------
    "morning_star": dict(name="明けの明星", en="Morning Star", cat="3本組", rank="S", sig="long",
        m="大陰線→窓を空けた小さな星→大陽線。下落→迷い→買い転換。底の最重要。", e="下落後・サポートで3本目大陽線確定で買い。",
        s="真ん中の星の安値の下。", t="直近高値/RR1:2〜3。", fk="星が大きい/3本目が浅いと弱い。窓+深い回復ほど信頼大。"),
    "evening_star": dict(name="宵の明星", en="Evening Star", cat="3本組", rank="S", sig="short",
        m="大陽線→窓を空けた小さな星→大陰線。上昇→迷い→売り転換。天井の最重要。", e="上昇後・レジスタンスで3本目大陰線確定で売り。",
        s="真ん中の星の高値の上。", t="直近安値/RR1:2〜3。", fk="3本目の陰線が浅いと不発。深く差し込むほど強い。"),
    "abandoned_baby_bull": dict(name="捨て子線(強気)", en="Bullish Abandoned Baby", cat="3本組", rank="A", sig="long",
        m="真ん中が上下とも窓で完全に孤立した同事。稀だが反転信頼度が非常に高い。", e="下落後・節目で3本目確定→買い。",
        s="孤立した同事の安値の下。", t="直近高値/RR1:2〜3。", fk="FXでは窓が小さく成立は稀。出れば強い。"),
    "abandoned_baby_bear": dict(name="捨て子線(弱気)", en="Bearish Abandoned Baby", cat="3本組", rank="A", sig="short",
        m="真ん中が上下とも窓で完全に孤立した同事=天井。稀だが信頼度が非常に高い。", e="上昇後・節目で3本目確定→売り。",
        s="孤立した同事の高値の上。", t="直近安値/RR1:2〜3。", fk="FXでは窓が小さく成立は稀。出れば強い。"),
    "three_white_soldiers": dict(name="赤三兵", en="Three White Soldiers", cat="3本組", rank="A", sig="long",
        m="実体の大きい陽線が3本連続で切り上がる。安定した強い上昇開始。", e="安値圏/レンジ上抜けで3本確定→押し目を待って順張り買い。",
        s="3本目の安値、または直近押し安値。", t="トレンド終了まで(伸ばす)/RR1:2〜。", fk="高値圏の赤三兵は最後の上げの可能性。3本目の長上ヒゲは減速注意。"),
    "three_black_crows": dict(name="黒三兵(三羽烏)", en="Three Black Crows", cat="3本組", rank="A", sig="short",
        m="実体の大きい陰線が3本連続で切り下がる。本格的な下落開始。", e="高値圏/レンジ下抜けで3本確定→戻りを待って順張り売り。",
        s="3本目の高値、または直近戻り高値。", t="トレンド終了まで/RR1:2〜。", fk="安値圏の三羽烏は売られ過ぎ=反発注意。戻りで。"),
    "rising_three": dict(name="上げ三法", en="Rising Three Methods", cat="3本組", rank="B", sig="long",
        m="大陽線→小調整(陽線範囲内)→新高値の大陽線。上昇トレンド継続。", e="調整が1本目範囲を割らず5本目が高値更新で確定→順張り買い。",
        s="調整の安値(1本目大陽線の安値)の下。", t="トレンド継続中ホールド/直近高値更新。", fk="調整が1本目安値を割ったら不成立。トレンド明確時のみ。"),
    "falling_three": dict(name="下げ三法", en="Falling Three Methods", cat="3本組", rank="B", sig="short",
        m="大陰線→小戻り(陰線範囲内)→新安値の大陰線。下落トレンド継続。", e="戻りが1本目範囲を超えず5本目が安値更新で確定→順張り売り。",
        s="戻りの高値(1本目大陰線の高値)の上。", t="トレンド継続中ホールド/直近安値更新。", fk="戻りが1本目高値を超えたら不成立。"),
    "three_gaps_up": dict(name="三空踏み上げ", en="Three Gaps Up", cat="3本組", rank="C", sig="short",
        m="窓を空けながら連続上昇=買いの過熱(クライマックス)。上昇の終わりを警戒。", e="新規買い禁物。利確目安/天井反転の出現を待つ。",
        s="—(逆張り売りは確認必須)", t="—", fk="勢いが強いと更に伸びる。単体逆張りは危険。"),
    "three_gaps_down": dict(name="三空叩き込み", en="Three Gaps Down", cat="3本組", rank="C", sig="long",
        m="窓を空けながら連続下落=売りの過熱(セリクラ)。下落の終わりを警戒。", e="新規売り禁物。底反転の出現を待って買い。",
        s="—(確認必須)", t="—", fk="パニック下落は行き過ぎても続く。反転形+次足確認まで待つ。"),
    # ---------- チャート反転 ----------
    "chart_double_top": dict(name="ダブルトップ", en="Double Top", cat="チャート反転", rank="S", sig="short",
        m="同価格帯で2回高値をつけ、間の谷(ネックライン)を割って下落=強力天井反転。", e="ネックラインを15分足終値で下抜け確定で売り。戻りで入ると安全。",
        s="2つ目の山の高値の少し上。", t="山の高さをネックから下に投影/直近安値。", fk="ネック割れ前は未完成。2山の高値が大きくズレると無効。"),
    "chart_double_bottom": dict(name="ダブルボトム", en="Double Bottom", cat="チャート反転", rank="S", sig="long",
        m="同価格で2回安値をつけ、間の山(ネックライン)を上抜け=強力底反転。", e="ネックライン上抜け確定で買い。戻りで入ると安全。",
        s="2つ目の底の安値の少し下。", t="底の深さをネックから上に投影/直近高値。", fk="上抜け前は入らない。2底が大きくズレると無効。"),
    "chart_triple_top": dict(name="トリプルトップ", en="Triple Top", cat="チャート反転", rank="A", sig="short",
        m="高値を3回はね返されネックライン割れ=天井。", e="3山目で失速→ネックライン下抜け確定で売り。",
        s="直近の山の高値の上。", t="山の高さを下に投影/直近安値。", fk="3度目で上抜けると逆に強い上昇。割れ確定を待つ。"),
    "chart_triple_bottom": dict(name="トリプルボトム", en="Triple Bottom", cat="チャート反転", rank="A", sig="long",
        m="安値を3回支えられネックライン上抜け=底。", e="3底目で反発→ネックライン上抜け確定で買い。",
        s="直近の底の下。", t="深さを上に投影/直近高値。", fk="上抜け前は入らない。3度目で割れると下落加速。"),
    "chart_hs": dict(name="ヘッドアンドショルダー", en="Head & Shoulders", cat="チャート反転", rank="S", sig="short",
        m="左肩→頭(最高値)→右肩→ネック割れ。天井反転の最重要形。", e="ネックライン(2つの谷)を15分足終値で下抜けで売り。戻りで入ると安全。",
        s="右肩の高値の上。", t="頭からネックの高さを下に投影/直近安値。", fk="ネック割れ前は未完成。頭で出来高増・右肩で減ると信頼大。"),
    "chart_inv_hs": dict(name="逆ヘッドアンドショルダー", en="Inverse H&S", cat="チャート反転", rank="S", sig="long",
        m="逆三尊。底反転の最重要形。", e="ネックラインを15分足終値で上抜けで買い。戻りで入ると安全。",
        s="右肩の安値の下。", t="頭の深さを上に投影/直近高値。", fk="上抜け前は入らない。ダマシブレイクに注意、終値確定で判断。"),
    "chart_rising_wedge": dict(name="上昇ウェッジ", en="Rising Wedge", cat="チャート反転", rank="B", sig="short",
        m="高値も安値も切り上げるが収縮=上昇の勢い喪失。上げているのに売り。", e="下側ラインを15分足終値で下抜けで売り。",
        s="直近の戻り高値の上。", t="ウェッジ始点の安値/RR1:2。", fk="上昇継続に見えて騙されやすい。下抜け確定を待つ。"),
    "chart_falling_wedge": dict(name="下降ウェッジ", en="Falling Wedge", cat="チャート反転", rank="B", sig="long",
        m="安値も高値も切り下げるが収縮=下落の勢い喪失。下げているのに買い。", e="上側ラインを15分足終値で上抜けで買い。",
        s="直近の押し安値の下。", t="ウェッジ始点の高値/RR1:2。", fk="下落継続に見えて騙されやすい。上抜け確定を待つ。"),
    # ---------- チャート継続 ----------
    "chart_asc_triangle": dict(name="アセンディングトライアングル", en="Ascending Triangle", cat="チャート継続", rank="A", sig="long",
        m="高値が水平(強い抵抗)+安値切り上げ=買い圧力増。上抜けで上放れ。", e="水平上値ラインを15分足終値で上抜けで買い。戻りで安全。",
        s="直近の押し安値の下。", t="三角の高さを上に投影。", fk="上抜け前は入らない。安値切り上げライン割れなら逆に売り。"),
    "chart_desc_triangle": dict(name="ディセンディングトライアングル", en="Descending Triangle", cat="チャート継続", rank="A", sig="short",
        m="安値が水平(サポート)+高値切り下げ=売り圧力増。下抜けで下放れ。", e="水平下値ラインを15分足終値で下抜けで売り。戻りで安全。",
        s="直近の戻り高値の上。", t="三角の高さを下に投影。", fk="下抜け前は入らない。上放れなら逆に買い。"),
    "chart_sym_triangle": dict(name="対称三角(保ち合い)", en="Symmetrical Triangle", cat="チャート継続", rank="B", sig="neutral",
        m="高値切り下げ+安値切り上げで収縮=エネルギー蓄積。抜けた方向に走る。", e="上抜け→買い/下抜け→売り(15分足終値で確定方向に順張り)。",
        s="三角の反対側の直近高安。", t="三角の最大幅をブレイク点から投影。", fk="頂点間際の抜けはダマシ多発。早めの抜け+勢いが理想。"),
    "chart_rectangle": dict(name="レクタングル(レンジ)", en="Rectangle / Range", cat="チャート継続", rank="A", sig="neutral",
        m="水平の上限・下限を往復するレンジ。抜けた方向に放れる。", e="上限/下限を15分足終値でブレイクした方向に順張り。",
        s="ブレイク=反対の枠の外。", t="ボックスの高さをブレイク点から投影。", fk="ヒゲだけのダマシ抜けが頻発。終値確定+リターンムーブで。"),
    "chart_bull_flag": dict(name="上昇フラッグ", en="Bull Flag", cat="チャート継続", rank="A", sig="long",
        m="急騰(ポール)→緩やかに下る小休止→再上昇。強い上昇継続。", e="フラッグ上辺を15分足終値で上抜けで買い(順張り)。",
        s="フラッグ下辺の下。", t="ポールの値幅をブレイク点から上に投影。", fk="フラッグが深く下げ過ぎ/長すぎると失敗。浅い調整が理想。"),
    "chart_bear_flag": dict(name="下降フラッグ", en="Bear Flag", cat="チャート継続", rank="A", sig="short",
        m="急落(ポール)→緩やかに上る小休止→再下落。強い下落継続。", e="フラッグ下辺を15分足終値で下抜けで売り(順張り)。",
        s="フラッグ上辺の上。", t="ポールの値幅をブレイク点から下に投影。", fk="フラッグが深く上げ過ぎ/長すぎると失敗。浅い調整が理想。"),
    "chart_pennant_bull": dict(name="ペナント(上)", en="Bullish Pennant", cat="チャート継続", rank="A", sig="long",
        m="急騰→小さな三角の保ち合い→再上昇。フラッグの三角版。", e="ペナント上辺を15分足終値で上抜けで買い。",
        s="ペナント下辺の下。", t="ポール値幅を投影。", fk="保ち合いが長引くと勢い喪失。短期で抜けるのが理想。"),
    "chart_pennant_bear": dict(name="ペナント(下)", en="Bearish Pennant", cat="チャート継続", rank="A", sig="short",
        m="急落→小さな三角の保ち合い→再下落。フラッグの三角版。", e="ペナント下辺を15分足終値で下抜けで売り。",
        s="ペナント上辺の上。", t="ポール値幅を投影。", fk="保ち合いが長引くと勢い喪失。短期で抜けるのが理想。"),
    # ---------- トレンドの形 (ダウ理論) ----------
    "chart_dow_reversal_down": dict(name="トレンド転換(下)", en="Trend Reversal Down (Dow)", cat="トレンドの形", rank="A", sig="short",
        m="上昇中に高値を更新できず(高値切り下げ)→直近の押し安値を割る=上昇トレンド終了。", e="直近の重要な押し安値を15分足終値で下抜け→売り転換。",
        s="直近の戻り高値の上。", t="次の安値/前の上昇分の半値〜全戻し。", fk="一時的な割れ(ダマシ)に注意。構造転換+戻り売りで安全。"),
    "chart_dow_reversal_up": dict(name="トレンド転換(上)", en="Trend Reversal Up (Dow)", cat="トレンドの形", rank="A", sig="long",
        m="下降中に安値を更新できず(安値切り上げ)→直近の戻り高値を超える=下降トレンド終了。", e="直近の重要な戻り高値を15分足終値で上抜け→買い転換。",
        s="直近の押し安値の下。", t="次の高値/前の下落分の半値〜全戻し。", fk="一時的な超え(ダマシ)に注意。構造転換+押し目買いで安全。"),
    "chart_trendline_break_down": dict(name="トレンドライン割れ(下)", en="Trendline Break Down", cat="トレンドの形", rank="A", sig="short",
        m="安値を結んだ上昇トレンドラインを価格が割る=上昇の勢い終了/転換点。", e="トレンドライン(チャネル下限)を15分足終値で下抜け→売り。戻りで安全。",
        s="直近の戻り高値の上。", t="チャネル幅を下に投影/直近安値。", fk="ラインの引き方で精度が変わる。ヒゲ抜けだけは無効。"),
    "chart_trendline_break_up": dict(name="トレンドライン抜け(上)", en="Trendline Break Up", cat="トレンドの形", rank="A", sig="long",
        m="高値を結んだ下降トレンドラインを価格が上抜け=下落の勢い終了/転換点。", e="トレンドライン(チャネル上限)を15分足終値で上抜け→買い。戻りで安全。",
        s="直近の押し安値の下。", t="チャネル幅を上に投影/直近高値。", fk="ラインの引き方で精度が変わる。ヒゲ抜けだけは無効。"),
}


# ------------------------------------------------------------------ 幾何
class _C:
    __slots__ = ("o", "h", "l", "c", "body", "rng", "up", "lo", "bull", "bear")

    def __init__(self, row):
        self.o = float(row["Open"]); self.h = float(row["High"])
        self.l = float(row["Low"]); self.c = float(row["Close"])
        self.body = abs(self.c - self.o)
        self.rng = max(self.h - self.l, 1e-12)
        self.up = self.h - max(self.o, self.c)     # upper wick
        self.lo = min(self.o, self.c) - self.l     # lower wick
        self.bull = self.c > self.o
        self.bear = self.c < self.o

    def is_doji(self) -> bool:
        return self.body <= self.rng * 0.10

    def small(self) -> bool:
        return self.body <= self.rng * 0.34

    def big(self) -> bool:
        return self.body >= self.rng * 0.62


def _rows(df: pd.DataFrame, k: int):
    """末尾 k 本を _C のリストで返す (古い→新しい)。"""
    tail = df.tail(k)
    return [_C(tail.iloc[i]) for i in range(len(tail))]


def _prior_trend(df: pd.DataFrame, lookback: int = 12) -> str:
    """評価足の手前の地合い (反転系の前提)。'up'/'down'/'flat'。"""
    if df is None or len(df) < lookback + 2:
        return "flat"
    seg = df["Close"].iloc[-(lookback + 1):-1]
    if len(seg) < 4:
        return "flat"
    a, b = float(seg.iloc[0]), float(seg.iloc[-1])
    if a <= 0:
        return "flat"
    chg = (b - a) / a
    if chg > 0.0015:
        return "up"
    if chg < -0.0015:
        return "down"
    return "flat"


# ------------------------------------------------------------------ 検出
def detect(df: pd.DataFrame) -> list[dict]:
    """渡された df の最終行を評価足としてマッチしたパターンを返す。

    各要素: {key, sig('long'|'short'|'neutral'), strength(0-1),
             sl_hint(価格 or None), n_bars}
    """
    if df is None or len(df) < 6:
        return []
    out: list[dict] = []
    c1 = _C(df.iloc[-1])                       # 評価足 (確定足)
    c2 = _C(df.iloc[-2])
    c3 = _C(df.iloc[-3]) if len(df) >= 3 else None
    pt = _prior_trend(df)

    def add(key, sig, strength, sl_hint, n=1):
        out.append({"key": key, "sig": sig, "strength": float(max(0.0, min(1.0, strength))),
                    "sl_hint": sl_hint, "n_bars": n})

    # ===== 単体 =====
    # 丸坊主
    if c1.big() and c1.up < c1.rng * 0.08 and c1.lo < c1.rng * 0.08:
        if c1.bull:
            add("marubozu_bull", "long", c1.body / c1.rng, c1.l)
        elif c1.bear:
            add("marubozu_bear", "short", c1.body / c1.rng, c1.h)
    # コマ
    if c1.small() and c1.up > c1.body and c1.lo > c1.body and not c1.is_doji():
        add("spinning_top", "neutral", 0.3, None)
    # 同事系
    if c1.is_doji():
        if c1.lo > c1.rng * 0.6 and c1.up < c1.rng * 0.15:
            add("dragonfly_doji", "long", c1.lo / c1.rng, c1.l)
        elif c1.up > c1.rng * 0.6 and c1.lo < c1.rng * 0.15:
            add("gravestone_doji", "short", c1.up / c1.rng, c1.h)
        elif c1.up > c1.rng * 0.33 and c1.lo > c1.rng * 0.33:
            add("long_legged_doji", "neutral", 0.4, None)
        else:
            add("doji", "neutral", 0.3, None)
    # ハンマー / 首吊り / 逆ハンマー / 流れ星 / ピンバー
    # 下ヒゲ/上ヒゲがレンジの半分以上 + 小実体 + 反対側ヒゲは僅少 (レンジ基準)
    long_lower = (c1.lo >= c1.rng * 0.50 and c1.up <= c1.rng * 0.20
                  and c1.body <= c1.rng * 0.40 and not c1.is_doji())
    long_upper = (c1.up >= c1.rng * 0.50 and c1.lo <= c1.rng * 0.20
                  and c1.body <= c1.rng * 0.40 and not c1.is_doji())
    if long_lower:
        if pt == "down":
            add("hammer", "long", min(1.0, c1.lo / c1.rng), c1.l)
        elif pt == "up":
            add("hanging_man", "short", min(1.0, c1.lo / c1.rng), c1.h)
    if long_upper:
        if pt == "up":
            add("shooting_star", "short", min(1.0, c1.up / c1.rng), c1.h)
        elif pt == "down":
            add("inverted_hammer", "long", min(1.0, c1.up / c1.rng), c1.l)
    # ピンバー (ヒゲがレンジの過半 — 強い拒絶)。S ランク。
    if c1.lo > c1.rng * 0.55 and c1.body < c1.rng * 0.35:
        add("pin_bar_bull", "long", c1.lo / c1.rng, c1.l)
    if c1.up > c1.rng * 0.55 and c1.body < c1.rng * 0.35:
        add("pin_bar_bear", "short", c1.up / c1.rng, c1.h)

    # ===== 2本組 (c2=前足, c1=評価足) =====
    # 包み足
    if c2.bear and c1.bull and c1.c >= c2.o and c1.o <= c2.c and c1.body > c2.body:
        add("engulf_bull", "long", min(1.0, c1.body / max(c2.body, 1e-9) / 2), min(c1.l, c2.l), 2)
    if c2.bull and c1.bear and c1.c <= c2.o and c1.o >= c2.c and c1.body > c2.body:
        add("engulf_bear", "short", min(1.0, c1.body / max(c2.body, 1e-9) / 2), max(c1.h, c2.h), 2)
    # はらみ / はらみ寄せ
    inside = (max(c1.o, c1.c) <= max(c2.o, c2.c)) and (min(c1.o, c1.c) >= min(c2.o, c2.c))
    if c2.big() and inside and c1.body < c2.body:
        if c2.bear:  # 下落後の反転初期
            if c1.is_doji():
                add("harami_cross_bull", "long", 0.7, c2.l, 2)
            elif c1.bull:
                add("harami_bull", "long", 0.5, c2.l, 2)
        elif c2.bull:
            if c1.is_doji():
                add("harami_cross_bear", "short", 0.7, c2.h, 2)
            elif c1.bear:
                add("harami_bear", "short", 0.5, c2.h, 2)
    # かぶせ線 / 切り込み線 (窓 + 中値割込み/超え)
    c2mid = (c2.o + c2.c) / 2
    if c2.bull and c1.bear and c1.o > c2.h and c2.c < c1.o and c1.c < c2mid and c1.c > c2.o:
        add("dark_cloud_cover", "short", 0.7, max(c1.h, c2.h), 2)
    if c2.bear and c1.bull and c1.o < c2.l and c1.c > c2mid and c1.c < c2.o:
        add("piercing_line", "long", 0.7, min(c1.l, c2.l), 2)
    # 毛抜き
    tol = max(c1.rng, c2.rng) * 0.12
    if abs(c1.h - c2.h) <= tol and c2.bull and c1.bear and pt == "up":
        add("tweezer_top", "short", 0.7, max(c1.h, c2.h) + tol * 0.2, 2)
    if abs(c1.l - c2.l) <= tol and c2.bear and c1.bull and pt == "down":
        add("tweezer_bottom", "long", 0.7, min(c1.l, c2.l) - tol * 0.2, 2)
    # 出会い線 (逆方向の大足が前足終値付近で止まる)
    ctol = max(c1.rng, c2.rng) * 0.10
    if c2.bear and c1.bull and c1.big() and abs(c1.c - c2.c) <= ctol and pt == "down":
        add("counterattack_bull", "long", 0.45, min(c1.l, c2.l), 2)
    if c2.bull and c1.bear and c1.big() and abs(c1.c - c2.c) <= ctol and pt == "up":
        add("counterattack_bear", "short", 0.45, max(c1.h, c2.h), 2)
    # たすき (継続: 窓 + 浅い逆行)
    if pt == "up" and c2.bull and c1.bear and c2.o > _C(df.iloc[-3]).c and c1.c > _C(df.iloc[-3]).c and c1.body < c2.body:
        add("tasuki_up", "long", 0.5, c1.l, 2)
    if pt == "down" and c2.bear and c1.bull and c2.o < _C(df.iloc[-3]).c and c1.c < _C(df.iloc[-3]).c and c1.body < c2.body:
        add("tasuki_down", "short", 0.5, c1.h, 2)

    # ===== 3本組 (c3,c2,c1) =====
    if c3 is not None:
        # 明けの明星 / 宵の明星
        if c3.bear and c3.big() and c2.small() and c1.bull and c1.big() and c1.c > (c3.o + c3.c) / 2 and pt == "down":
            add("morning_star", "long", 0.85, min(c3.l, c2.l, c1.l), 3)
        if c3.bull and c3.big() and c2.small() and c1.bear and c1.big() and c1.c < (c3.o + c3.c) / 2 and pt == "up":
            add("evening_star", "short", 0.85, max(c3.h, c2.h, c1.h), 3)
        # 捨て子線 (中央が窓で孤立した同事)
        if c2.is_doji() and c2.h < min(c3.l, c1.l) and c3.bear and c1.bull and pt == "down":
            add("abandoned_baby_bull", "long", 0.8, c2.l, 3)
        if c2.is_doji() and c2.l > max(c3.h, c1.h) and c3.bull and c1.bear and pt == "up":
            add("abandoned_baby_bear", "short", 0.8, c2.h, 3)
        # 赤三兵 / 黒三兵
        if (c3.bull and c2.bull and c1.bull and c1.c > c2.c > c3.c
                and c2.o > c3.o and c1.o > c2.o and c3.big() and c2.big() and c1.big()):
            add("three_white_soldiers", "long", 0.8, min(c3.l, c2.l, c1.l), 3)
        if (c3.bear and c2.bear and c1.bear and c1.c < c2.c < c3.c
                and c2.o < c3.o and c1.o < c2.o and c3.big() and c2.big() and c1.big()):
            add("three_black_crows", "short", 0.8, max(c3.h, c2.h, c1.h), 3)
        # 三空 (連続窓 = 過熱)
        if len(df) >= 4:
            c0 = _C(df.iloc[-4])
            if c0.l > _C(df.iloc[-5]).h if len(df) >= 5 else False:
                pass
            if c3.l > c0.h and c2.l > c3.h and c1.l > c2.h:
                add("three_gaps_up", "short", 0.4, None, 3)
            if c3.h < c0.l and c2.h < c3.l and c1.h < c2.l:
                add("three_gaps_down", "long", 0.4, None, 3)

    # ===== 上げ/下げ三法 (5本: 大足 + 調整3 + 大足) =====
    if len(df) >= 5:
        b = _rows(df, 5)  # 古→新
        a0, mid, a4 = b[0], b[1:4], b[4]
        if a0.bull and a0.big() and all(x.body < a0.body for x in mid) and \
           all(min(x.o, x.c) > a0.o for x in mid) and a4.bull and a4.c > a0.c and a4.big():
            add("rising_three", "long", 0.55, min(x.l for x in b), 5)
        if a0.bear and a0.big() and all(x.body < a0.body for x in mid) and \
           all(max(x.o, x.c) < a0.o for x in mid) and a4.bear and a4.c < a0.c and a4.big():
            add("falling_three", "short", 0.55, max(x.h for x in b), 5)

    # ===== Phase 2: チャート/構造パターン (スイング幾何) =====
    out.extend(_detect_chart(df))

    return out


# ------------------------------------------------------------------ Phase2
def _approx(a: float, b: float, tol: float = 0.0022) -> bool:
    m = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / m <= tol


def _detect_chart(df: pd.DataFrame) -> list[dict]:
    """スイング幾何ベースのチャートパターン検出 (確定ブレイクで成立)。

    出典 HTML「チャート反転/継続/トレンドの形」。最終足 = 評価足。
    ブレイク確定 (= 評価足の終値がネック/ライン/枠を抜けた) を必須にし、
    未完成の形では発火しない。
    """
    res: list[dict] = []
    if df is None or len(df) < 50:
        return res
    win = df.tail(180)
    c = float(win["Close"].iloc[-1])
    last_h = float(win["High"].iloc[-1])
    last_l = float(win["Low"].iloc[-1])
    eps = c * 0.0004 if c else 0.0  # 終値ブレイク判定の最小マージン

    sh, sl = find_swings(win, window=3)  # [(idx, price), ...]

    def push(key, sig, strength, sl_hint, span):
        res.append({"key": key, "sig": sig,
                    "strength": float(max(0.0, min(1.0, strength))),
                    "sl_hint": sl_hint, "n_bars": int(span)})

    # ---- ダブル / トリプル トップ・ボトム ----
    if len(sh) >= 2 and len(sl) >= 1:
        (i1, p1), (i2, p2) = sh[-2], sh[-1]
        troughs = [pr for ix, pr in sl if i1 < ix < i2]
        if troughs and _approx(p1, p2, 0.0026):
            neck = min(troughs)
            if c < neck - eps:  # ネック割れ確定
                push("chart_double_top", "short",
                     0.85 - abs(p1 - p2) / max(p1, 1e-9) * 40,
                     max(p1, p2), i2 - i1)
    if len(sl) >= 2 and len(sh) >= 1:
        (i1, q1), (i2, q2) = sl[-2], sl[-1]
        peaks = [pr for ix, pr in sh if i1 < ix < i2]
        if peaks and _approx(q1, q2, 0.0026):
            neck = max(peaks)
            if c > neck + eps:
                push("chart_double_bottom", "long",
                     0.85 - abs(q1 - q2) / max(q1, 1e-9) * 40,
                     min(q1, q2), i2 - i1)
    if len(sh) >= 3 and len(sl) >= 2:
        a, b3, d = sh[-3][1], sh[-2][1], sh[-1][1]
        if _approx(a, b3, 0.003) and _approx(b3, d, 0.003):
            necks = [pr for ix, pr in sl if sh[-3][0] < ix < sh[-1][0]]
            if necks and c < min(necks) - eps:
                push("chart_triple_top", "short", 0.7, max(a, b3, d), sh[-1][0] - sh[-3][0])
    if len(sl) >= 3 and len(sh) >= 2:
        a, b3, d = sl[-3][1], sl[-2][1], sl[-1][1]
        if _approx(a, b3, 0.003) and _approx(b3, d, 0.003):
            necks = [pr for ix, pr in sh if sl[-3][0] < ix < sl[-1][0]]
            if necks and c > max(necks) + eps:
                push("chart_triple_bottom", "long", 0.7, min(a, b3, d), sl[-1][0] - sl[-3][0])

    # ---- ヘッド&ショルダー / 逆 ----
    if len(sh) >= 3 and len(sl) >= 2:
        ls, head, rs = sh[-3][1], sh[-2][1], sh[-1][1]
        if head > ls and head > rs and _approx(ls, rs, 0.04):
            necks = [pr for ix, pr in sl if sh[-3][0] < ix < sh[-1][0]]
            if len(necks) >= 1 and c < min(necks) - eps:
                push("chart_hs", "short", 0.85, max(rs, head), sh[-1][0] - sh[-3][0])
    if len(sl) >= 3 and len(sh) >= 2:
        ls, head, rs = sl[-3][1], sl[-2][1], sl[-1][1]
        if head < ls and head < rs and _approx(ls, rs, 0.04):
            necks = [pr for ix, pr in sh if sl[-3][0] < ix < sl[-1][0]]
            if len(necks) >= 1 and c > max(necks) + eps:
                push("chart_inv_hs", "long", 0.85, min(rs, head), sl[-1][0] - sl[-3][0])

    # ---- 三角 / レンジ ----
    rh = [pr for _, pr in sh[-4:]]
    rl = [pr for _, pr in sl[-4:]]
    if len(rh) >= 2 and len(rl) >= 2:
        flat_top = cluster_levels(rh, tolerance_pct=0.0025)
        flat_bot = cluster_levels(rl, tolerance_pct=0.0025)
        hi_up = rh[-1] > rh[-2]
        hi_dn = rh[-1] < rh[-2]
        lo_up = rl[-1] > rl[-2]
        lo_dn = rl[-1] < rl[-2]
        # アセンディング: 上限水平 + 安値切り上げ → 上抜け
        if flat_top and lo_up and c > max(flat_top) + eps:
            push("chart_asc_triangle", "long", 0.7, rl[-1], 30)
        # ディセンディング: 下限水平 + 高値切り下げ → 下抜け
        if flat_bot and hi_dn and c < min(flat_bot) - eps:
            push("chart_desc_triangle", "short", 0.7, rh[-1], 30)
        # 対称三角: 高値切り下げ + 安値切り上げ → 抜けた方向
        if hi_dn and lo_up:
            if c > rh[-1] + eps:
                push("chart_sym_triangle", "long", 0.5, rl[-1], 30)
            elif c < rl[-1] - eps:
                push("chart_sym_triangle", "short", 0.5, rh[-1], 30)
        # レンジ: 上下とも水平クラスタ → ブレイク方向
        if flat_top and flat_bot:
            bt, bb = max(flat_top), min(flat_bot)
            if bt > bb:
                if c > bt + eps:
                    push("chart_rectangle", "long", 0.6, bt, 30)
                elif c < bb - eps:
                    push("chart_rectangle", "short", 0.6, bb, 30)
        # ウェッジ
        if rh[-1] > rh[-2] and rl[-1] > rl[-2] and c < rl[-1] - eps:
            push("chart_rising_wedge", "short", 0.45, rh[-1], 30)
        if rh[-1] < rh[-2] and rl[-1] < rl[-2] and c > rh[-1] + eps:
            push("chart_falling_wedge", "long", 0.45, rl[-1], 30)

    # ---- フラッグ / ペナント (ポール + 浅い保ち合い + ブレイク) ----
    if len(win) >= 22:
        closes = win["Close"].values
        pole_a, pole_b = float(closes[-18]), float(closes[-7])
        cons = win.iloc[-6:-1]
        cons_hi = float(cons["High"].max())
        cons_lo = float(cons["Low"].min())
        cons_rng = cons_hi - cons_lo
        pole_up = (pole_b - pole_a) / max(abs(pole_a), 1e-9)
        if pole_up > 0.004 and cons_rng < abs(pole_b - pole_a) * 0.6 and c > cons_hi + eps:
            ch = [pr for _, pr in sh[-2:]]
            cl = [pr for _, pr in sl[-2:]]
            converging = len(ch) == 2 and len(cl) == 2 and ch[-1] < ch[-2] and cl[-1] > cl[-2]
            push("chart_pennant_bull" if converging else "chart_bull_flag",
                 "long", 0.6, cons_lo, 18)
        if pole_up < -0.004 and cons_rng < abs(pole_b - pole_a) * 0.6 and c < cons_lo - eps:
            ch = [pr for _, pr in sh[-2:]]
            cl = [pr for _, pr in sl[-2:]]
            converging = len(ch) == 2 and len(cl) == 2 and ch[-1] < ch[-2] and cl[-1] > cl[-2]
            push("chart_pennant_bear" if converging else "chart_bear_flag",
                 "short", 0.6, cons_hi, 18)

    # ---- ダウ トレンド転換 ----
    if len(sh) >= 2 and len(sl) >= 1:
        if sh[-1][1] < sh[-2][1] and c < sl[-1][1] - eps:   # 高値切り下げ + 押し安値割れ
            push("chart_dow_reversal_down", "short", 0.7, sh[-1][1], 40)
    if len(sl) >= 2 and len(sh) >= 1:
        if sl[-1][1] > sl[-2][1] and c > sh[-1][1] + eps:   # 安値切り上げ + 戻り高値超え
            push("chart_dow_reversal_up", "long", 0.7, sl[-1][1], 40)

    # ---- トレンドライン / チャネル割れ (直近2スイングの線形補外) ----
    n = len(win)
    if len(sl) >= 2:
        (xa, ya), (xb, yb) = sl[-2], sl[-1]
        if xb > xa and yb > ya:  # 上昇支持線
            slope = (yb - ya) / (xb - xa)
            proj = yb + slope * (n - 1 - xb)
            if c < proj - eps:
                push("chart_trendline_break_down", "short", 0.6, sh[-1][1] if sh else last_h, n - 1 - xa)
    if len(sh) >= 2:
        (xa, ya), (xb, yb) = sh[-2], sh[-1]
        if xb > xa and yb < ya:  # 下降抵抗線
            slope = (yb - ya) / (xb - xa)
            proj = yb + slope * (n - 1 - xb)
            if c > proj + eps:
                push("chart_trendline_break_up", "long", 0.6, sl[-1][1] if sl else last_l, n - 1 - xa)

    return res


def lo_idx_price(swing_lows):
    """find_swings の swing_lows をそのまま (idx, price) で返す薄いラッパ。"""
    return swing_lows


def rank_of(key: str) -> str:
    return PATTERN_META.get(key, {}).get("rank", "C")


def meta_of(key: str) -> dict:
    return PATTERN_META.get(key, {})
