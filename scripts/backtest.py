"""バックテスト CLI エントリ。

使い方:
    # 全ペア × 全手法 × 過去 6 か月 (デフォルト)
    python scripts/backtest.py

    # 単一ペア集中検証
    python scripts/backtest.py --pair USD/JPY --method triple --period 1y

    # 評価ステップを 4 → 1 にして精密化 (遅くなる)
    python scripts/backtest.py --sample-step 1

    # スコア閾値変更
    python scripts/backtest.py --threshold 65

出力:
    backtest/results/index.html  ← ブラウザで開く
    backtest/results/results.json ← 生データ
    backtest/results/trades.csv  ← 全トレード csv
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from data_fetcher import fetch_all  # noqa: E402
from backtest.engine import run_backtest, METHOD_NAMES  # noqa: E402
from backtest.metrics import compute_stats, Stats  # noqa: E402
from backtest.report import write_html, write_csv, write_json  # noqa: E402


RESULTS_DIR = ROOT / "backtest" / "results"


def parse_args():
    p = argparse.ArgumentParser(description="FX Signal バックテスト")
    p.add_argument("--pair", help="例: USD/JPY (省略時は全 15 ペア)")
    p.add_argument("--method", choices=list(METHOD_NAMES) + ["all"], default="all",
                   help="検証する手法 (既定: all)")
    p.add_argument("--period", default="6mo",
                   help="期間 (yfinance 形式: 1mo, 3mo, 6mo, 1y, 2y)")
    p.add_argument("--threshold", type=int, default=config.ALERT_THRESHOLD,
                   help=f"スコア閾値 (既定: {config.ALERT_THRESHOLD})")
    p.add_argument("--sample-step", type=int, default=4,
                   help="15M バーの何本ごとに評価するか (既定: 4 = 1時間ごと)")
    p.add_argument("--min-bars", type=int, default=200,
                   help="ウォームアップバー数 (これより前は評価しない)")
    p.add_argument("--tp-rr", type=float, default=None,
                   help="TP を R-multiple で固定上書き (例: 3.0)")
    p.add_argument("--min-rr", type=float, default=2.0,
                   help="tp_rr 未指定時の最低RR床 (既定 2.0、本番 api と一致)")
    p.add_argument("--emit-whitelist", action="store_true",
                   help="n>=min-n & PF>=min-pf & EV>0 の (手法,ペア) を state/ev_whitelist.json に書き出す")
    p.add_argument("--min-n", type=int, default=20, help="ホワイトリスト採用の最小サンプル数")
    p.add_argument("--min-pf", type=float, default=1.10, help="ホワイトリスト採用の最小 PF")
    p.add_argument("--verbose", "-v", action="store_true")
    return p.parse_args()


def _period_for(timeframe: str, period: str) -> str:
    """yfinance の interval ごとの最大期間を考慮した補正。

    各 TF は **可能な限り長く取得**し、バックテストの実効期間は
    短期足の min_bars 以降 (= ウォームアップ後) で自動的に絞られる。

    制限:
      1m  : 7d まで
      15m : 60d まで (= 15M で取れる最大、これがバックテスト期間の上限)
      1h  : 730d まで
      1d  : 制限なし
    """
    if timeframe == "1d":
        # 日足はウォームアップに 100 bars 以上必要 → 最低 6 ヶ月、安全のため 2 年
        return "2y"
    if timeframe == "15m":
        # 15M は 60 日 max。--period 引数で短くするのは可
        if period in ("7d", "14d", "30d", "1mo", "60d"):
            return period
        return "60d"
    if timeframe == "1h":
        # 1H は 730 日 max。ウォームアップに余裕を持って 2 年分
        return "730d"
    return period


def main():
    args = parse_args()
    started_total = time.monotonic()

    # 対象ペアと手法を決定
    pairs = (
        [(args.pair, config.PAIRS[args.pair])] if args.pair else list(config.PAIRS.items())
    )
    methods = list(METHOD_NAMES) if args.method == "all" else [args.method]

    print(f"[backtest] {len(pairs)} ペア × {len(methods)} 手法 × {args.period}")
    print(f"[backtest] sample_step={args.sample_step} (15M バーの {args.sample_step} 本ごとに評価)")
    print(f"[backtest] threshold={args.threshold}")
    if args.tp_rr is not None:
        print(f"[backtest] TP override: {args.tp_rr}R (entry ± {args.tp_rr} × |entry - SL|)")
    else:
        print(f"[backtest] TP: 構造的 (strategy 由来)")
    print()

    symbols = [s for _, s in pairs]

    # ---- データ取得 (3+1 時間軸) ----
    print("[backtest] yfinance データ取得中 (long/mid/h1/short)...")
    t0 = time.monotonic()
    long_data, mid_data, h1_data, short_data = fetch_all(
        symbols,
        long_iv="1d", long_p=_period_for("1d", args.period), long_rs=None,
        mid_iv="1h", mid_p=_period_for("1h", args.period), mid_rs="4h",
        short_iv="15m", short_p=_period_for("15m", args.period), short_rs=None,
        h1_iv="1h", h1_p=_period_for("1h", args.period), h1_rs=None,
    )

    # タイムゾーン統一: 一部 TF は tz-aware、一部は tz-naive で返ってくるので
    # 全部 tz-naive (UTC ベース) に揃える。strategy.py は tz を見ないので OK。
    def _strip_tz(d):
        if d is None or d.empty:
            return d
        if d.index.tz is not None:
            return d.tz_convert("UTC").tz_localize(None)
        return d

    for store in (long_data, mid_data, h1_data, short_data):
        for k in list(store.keys()):
            store[k] = _strip_tz(store[k])

    print(f"[backtest] データ取得完了 ({time.monotonic() - t0:.1f}s)")

    # ---- バックテスト実行 ----
    results = []
    stats_by_pm = {}
    aggregate_trades_by_method = {m: [] for m in methods}

    for pair, symbol in pairs:
        df_long = long_data.get(symbol)
        df_mid = mid_data.get(symbol)
        df_h1 = h1_data.get(symbol)
        df_short = short_data.get(symbol)

        if df_long is None or df_mid is None or df_short is None:
            print(f"[backtest] SKIP {pair}: データ取得失敗")
            continue
        if len(df_long) < 100 or len(df_mid) < 100 or len(df_short) < args.min_bars + 10:
            print(f"[backtest] SKIP {pair}: データ不足 (lt={len(df_long)} mt={len(df_mid)} st={len(df_short)})")
            continue

        for method in methods:
            t1 = time.monotonic()
            res = run_backtest(
                pair, symbol, method,
                df_long, df_mid, df_h1, df_short,
                threshold=args.threshold,
                sample_step=args.sample_step,
                min_bars=args.min_bars,
                verbose=args.verbose,
                tp_rr=args.tp_rr,
                min_rr=args.min_rr,
            )
            results.append(res)
            stats = compute_stats(res.trades)
            stats_by_pm[(pair, method)] = stats
            aggregate_trades_by_method[method].extend(res.trades)
            print(f"[backtest] {pair:10s} {method:8s}  trades={stats.trades:3d}  "
                  f"WR={stats.win_rate:5.1f}%  PF={stats.profit_factor:5.2f}  "
                  f"EV={stats.expectancy_r:+.3f}R  totalR={stats.total_r:+.1f}  "
                  f"({time.monotonic() - t1:.1f}s)")

    # ---- 手法別集計 ----
    aggregate_by_method = {
        m: compute_stats(trades) for m, trades in aggregate_trades_by_method.items()
    }

    # ---- 出力 ----
    print()
    print("[backtest] レポート生成中...")
    write_html(results, stats_by_pm, aggregate_by_method, RESULTS_DIR / "index.html")
    write_csv(
        [t for r in results for t in r.trades],
        RESULTS_DIR / "trades.csv",
    )
    write_json(results, stats_by_pm, RESULTS_DIR / "results.json")

    elapsed = time.monotonic() - started_total
    print(f"[backtest] 完了 ({elapsed:.1f}s)")
    print()
    print("=" * 60)
    print(" 手法別サマリ (全ペア合算)")
    print("=" * 60)
    print(f" {'手法':<8} {'件数':>5} {'勝率':>7} {'PF':>6} {'EV(R)':>8} {'累積R':>7} {'最大DD':>7}")
    print("-" * 60)
    for m in methods:
        s = aggregate_by_method[m]
        flag = " ★" if s.is_positive_ev and s.trades >= 10 else ""
        print(f" {m.upper():<8} {s.trades:>5d} {s.win_rate:>6.1f}% {s.profit_factor:>6.2f} "
              f"{s.expectancy_r:>+8.3f} {s.total_r:>+7.1f} {s.max_dd_r:>7.1f}{flag}")
    print("=" * 60)
    print()
    print(f"📊 詳細レポート: {RESULTS_DIR / 'index.html'}")
    print(f"   ブラウザで開く: open {RESULTS_DIR / 'index.html'}")

    # ---- +EV ホワイトリスト生成 (--emit-whitelist) ----
    if args.emit_whitelist:
        emit_whitelist(stats_by_pm, args)


def emit_whitelist(stats_by_pm: dict, args) -> None:
    """(手法,ペア) ごとの成績から +EV だけを state/ev_whitelist.json に書き出す。

    採用条件: n>=min_n かつ PF>=min_pf かつ EV>0。
    pa は strategy_pa が pair×pattern で自己ゲートするため、ここでは除外
    (ev_whitelist.is_pair_allowed が "pa" を素通しにする)。
    """
    import json
    from datetime import datetime, timezone

    out = ROOT / "state" / "ev_whitelist.json"
    entries: dict[str, dict] = {}
    for (pair, method), s in stats_by_pm.items():
        if method == "pa":
            continue
        if s.trades >= args.min_n and s.profit_factor >= args.min_pf and s.expectancy_r > 0:
            pf = round(s.profit_factor, 2) if s.profit_factor != float("inf") else 999.0
            entries[f"{method}|{pair}"] = {
                "n": s.trades,
                "wr": round(s.win_rate, 1),
                "pf": pf,
                "ev": round(s.expectancy_r, 3),
            }
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period": args.period,
        "min_rr": args.min_rr,
        "min_n": args.min_n,
        "min_pf": args.min_pf,
        "threshold": args.threshold,
        "entries": entries,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print(f"✅ EV ホワイトリスト {len(entries)} 件 → {out}")
    by_method: dict[str, list[str]] = {}
    for k in entries:
        m, p = k.split("|", 1)
        by_method.setdefault(m, []).append(p)
    for m, ps in sorted(by_method.items()):
        print(f"   {m:8s}: {', '.join(sorted(ps))}")


if __name__ == "__main__":
    main()
