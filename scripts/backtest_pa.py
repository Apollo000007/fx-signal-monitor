"""PA 手法 — ペア×パターン個別バックテスト → EV ホワイトリスト生成。

勝率を最大化する核心スクリプト:
  全ローソク足パターンを過去データで pair×pattern 単位に検証し、
  「実データで +EV と確認できた組合せ」だけを state/pa_whitelist.json に登録。
  strategy_pa.analyze_pair_pa はこの組合せだけ is_alert する。

使い方:
    python scripts/backtest_pa.py                 # 全15ペア・60日
    python scripts/backtest_pa.py --period 60d --min-n 20 --min-pf 1.1
    python scripts/backtest_pa.py --pair USD/JPY -v

出力:
    state/pa_whitelist.json     ← strategy_pa が読む有効化リスト
    backtest/PA_FINDINGS.md     ← パターン別の成績レポート
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# パターン機構の純 EV を測る (whitelist/指標抑制を外す)
os.environ["PA_BACKTEST_DISCOVERY"] = "1"

import config  # noqa: E402
from data_fetcher import fetch_all  # noqa: E402
from backtest.engine import run_backtest  # noqa: E402
from backtest.metrics import compute_stats  # noqa: E402
import patterns as pat  # noqa: E402

WHITELIST_FILE = ROOT / "state" / "pa_whitelist.json"
FINDINGS_FILE = ROOT / "backtest" / "PA_FINDINGS.md"


def parse_args():
    p = argparse.ArgumentParser(description="PA パターン別バックテスト")
    p.add_argument("--pair", help="例: USD/JPY (省略時は全 15 ペア)")
    p.add_argument("--period", default="60d", help="期間 (15M は最大 60d)")
    p.add_argument("--threshold", type=int, default=config.ALERT_THRESHOLD)
    p.add_argument("--sample-step", type=int, default=2,
                   help="15M バーの何本ごとに評価 (既定 2 = 30 分)")
    p.add_argument("--min-bars", type=int, default=200)
    p.add_argument("--min-n", type=int, default=20,
                   help="ホワイトリスト採用の最小サンプル数 (既定 20)")
    p.add_argument("--min-pf", type=float, default=1.10,
                   help="ホワイトリスト採用の最小 Profit Factor (既定 1.10)")
    p.add_argument("--verbose", "-v", action="store_true")
    return p.parse_args()


def _period_for(tf: str, period: str) -> str:
    if tf == "1d":
        return "2y"
    if tf == "15m":
        return period if period in ("7d", "14d", "30d", "1mo", "60d") else "60d"
    if tf == "1h":
        return "730d"
    return period


def _strip_tz(d):
    if d is None or d.empty:
        return d
    if d.index.tz is not None:
        return d.tz_convert("UTC").tz_localize(None)
    return d


def main() -> int:
    args = parse_args()
    t_all = time.monotonic()
    pairs = ([(args.pair, config.PAIRS[args.pair])] if args.pair
             else list(config.PAIRS.items()))
    symbols = [s for _, s in pairs]

    print(f"[pa-bt] {len(pairs)} ペア × PA × {args.period} "
          f"(min_n={args.min_n} min_pf={args.min_pf})")
    print("[pa-bt] データ取得中 (long/mid/h1/short)...")
    t0 = time.monotonic()
    long_d, mid_d, h1_d, short_d = fetch_all(
        symbols,
        long_iv="1d", long_p=_period_for("1d", args.period), long_rs=None,
        mid_iv="1h", mid_p=_period_for("1h", args.period), mid_rs="4h",
        short_iv="15m", short_p=_period_for("15m", args.period), short_rs=None,
        h1_iv="1h", h1_p=_period_for("1h", args.period), h1_rs=None,
    )
    for store in (long_d, mid_d, h1_d, short_d):
        for k in list(store.keys()):
            store[k] = _strip_tz(store[k])
    print(f"[pa-bt] 取得完了 ({time.monotonic() - t0:.1f}s)")

    # (pair, pattern) → [Trade]
    by_pp: dict[tuple[str, str], list] = defaultdict(list)
    by_pat: dict[str, list] = defaultdict(list)
    all_trades: list = []

    for pair, symbol in pairs:
        dl, dm, dh, ds = (long_d.get(symbol), mid_d.get(symbol),
                          h1_d.get(symbol), short_d.get(symbol))
        if dl is None or dm is None or ds is None:
            print(f"[pa-bt] SKIP {pair}: データ取得失敗")
            continue
        if len(dl) < 100 or len(dm) < 100 or len(ds) < args.min_bars + 10:
            print(f"[pa-bt] SKIP {pair}: データ不足")
            continue
        t1 = time.monotonic()
        res = run_backtest(
            pair, symbol, "pa", dl, dm, dh, ds,
            threshold=args.threshold, sample_step=args.sample_step,
            min_bars=args.min_bars, verbose=args.verbose, tp_rr=None,
        )
        for tr in res.trades:
            key = tr.pattern or "unknown"
            by_pp[(pair, key)].append(tr)
            by_pat[key].append(tr)
            all_trades.append(tr)
        st = compute_stats(res.trades)
        print(f"[pa-bt] {pair:10s}  trades={st.trades:3d}  WR={st.win_rate:5.1f}%  "
              f"PF={st.profit_factor:5.2f}  EV={st.expectancy_r:+.3f}R  "
              f"({time.monotonic() - t1:.1f}s)")

    # ---- ホワイトリスト判定 ----
    entries: dict[str, dict] = {}
    rows: list[tuple] = []
    for (pair, key), trs in sorted(by_pp.items()):
        s = compute_stats(trs)
        rank = pat.rank_of(key)
        name = pat.meta_of(key).get("name", key)
        ok = (s.trades >= args.min_n and s.profit_factor >= args.min_pf
              and s.expectancy_r > 0)
        rows.append((pair, key, name, rank, s, ok))
        if ok:
            entries[f"{pair}|{key}"] = {
                "n": s.trades, "wr": round(s.win_rate, 1),
                "pf": round(s.profit_factor, 2) if s.profit_factor != float("inf") else 999.0,
                "ev": round(s.expectancy_r, 3),
            }

    WHITELIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period": args.period,
        "min_n": args.min_n,
        "min_pf": args.min_pf,
        "threshold": args.threshold,
        "entries": entries,
    }
    WHITELIST_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                              encoding="utf-8")

    # ---- レポート ----
    lines = [
        "# PA (ローソク足パターン) バックテスト結果",
        "",
        f"- 生成: {payload['generated_at']}",
        f"- 期間: {args.period} / sample_step={args.sample_step} / threshold={args.threshold}",
        f"- 採用条件: n≥{args.min_n} かつ PF≥{args.min_pf} かつ EV>0",
        f"- **採用 (ホワイトリスト登録): {len(entries)} 組合せ**",
        "",
        "## パターン別 集計 (全ペア合算)",
        "",
        "| パターン | ランク | trades | WR% | PF | EV(R) | totalR |",
        "|---|---|--:|--:|--:|--:|--:|",
    ]
    for key, trs in sorted(by_pat.items(),
                           key=lambda kv: compute_stats(kv[1]).expectancy_r,
                           reverse=True):
        s = compute_stats(trs)
        pf = "∞" if s.profit_factor == float("inf") else f"{s.profit_factor:.2f}"
        lines.append(f"| {pat.meta_of(key).get('name', key)} ({key}) | "
                     f"{pat.rank_of(key)} | {s.trades} | {s.win_rate:.1f} | "
                     f"{pf} | {s.expectancy_r:+.3f} | {s.total_r:+.1f} |")

    lines += ["", "## ペア×パターン 採用判定", "",
              "| ペア | パターン | ランク | trades | WR% | PF | EV(R) | 採用 |",
              "|---|---|---|--:|--:|--:|--:|:--:|"]
    for pair, key, name, rank, s, ok in sorted(rows, key=lambda r: (not r[5], r[0])):
        pf = "∞" if s.profit_factor == float("inf") else f"{s.profit_factor:.2f}"
        lines.append(f"| {pair} | {name} ({key}) | {rank} | {s.trades} | "
                     f"{s.win_rate:.1f} | {pf} | {s.expectancy_r:+.3f} | "
                     f"{'✅' if ok else '—'} |")

    lines += [
        "",
        "## 解釈・運用",
        "",
        "- ✅ の組合せのみ `state/pa_whitelist.json` に登録され、本番 PA "
        "アラートの対象になる（厳格運用）。",
        "- ホワイトリスト未生成/不在時は **S ランクのみ暫定許可**（誤爆抑制）。",
        "- サンプル < 20 は統計的に無意味 → 採用しない（過剰最適化回避）。",
        "- 定期再実行で陳腐化を防ぐ（相場構造は変化する）。",
        "- 注意: バックテストの優位性が Live で再現する保証はない。"
        "ペーパートレード/デモで二重確認すること。",
    ]
    FINDINGS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"\n[pa-bt] ホワイトリスト {len(entries)} 件 → {WHITELIST_FILE}")
    print(f"[pa-bt] レポート → {FINDINGS_FILE}")
    print(f"[pa-bt] 完了 ({time.monotonic() - t_all:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
