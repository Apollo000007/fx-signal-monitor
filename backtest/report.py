"""バックテスト結果を HTML レポート + CSV + JSON で出力。

matplotlib があれば equity curve と勝率ヒートマップを PNG で埋め込む。
無くても HTML テーブルだけは生成する (グレースフル劣化)。
"""
from __future__ import annotations

import base64
import csv
import io
import json
from pathlib import Path

from .engine import Trade, BacktestResult
from .metrics import Stats, compute_stats, equity_curve

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_PLT = True
except Exception:
    HAS_PLT = False


def _png_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def _equity_chart(trades: list[Trade], title: str) -> str:
    if not HAS_PLT or not trades:
        return ""
    curve = equity_curve(trades)
    if not curve:
        return ""
    fig, ax = plt.subplots(figsize=(8, 3))
    ax.plot(curve, linewidth=1.4, color="#a855f7")
    ax.fill_between(range(len(curve)), curve, 0, alpha=0.15, color="#a855f7")
    ax.axhline(0, color="#888", linewidth=0.8, linestyle="--")
    ax.set_title(title, fontsize=10)
    ax.set_xlabel("Trade #", fontsize=9)
    ax.set_ylabel("Cumulative R", fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    return _png_b64(fig)


def write_csv(trades: list[Trade], out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not trades:
        out_path.write_text("(no trades)\n", encoding="utf-8")
        return
    fields = list(trades[0].to_dict().keys())
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for t in trades:
            w.writerow(t.to_dict())


def write_json(results: list[BacktestResult], stats_by_pm: dict, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "results": [r.to_dict() for r in results],
        "stats": {f"{p}|{m}": s.to_dict() for (p, m), s in stats_by_pm.items()},
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------- HTML レポート ----------------

_CSS = """
body { font-family: -apple-system, system-ui, sans-serif; background: #0b0a1f; color: #f5ecd7; padding: 24px; max-width: 1400px; margin: 0 auto; }
h1, h2, h3 { color: #e9c46a; }
table { border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 12px; }
th, td { border: 1px solid #2a2247; padding: 6px 10px; text-align: right; }
th { background: #14122e; color: #c9b88a; font-weight: 600; text-align: center; }
td:first-child, th:first-child { text-align: left; }
.win { color: #4ade80; }
.loss { color: #e25c73; }
.muted { color: #7a6b9a; }
.section { margin: 32px 0; }
.badge-positive { background: #4ade80; color: #0b0a1f; padding: 2px 8px; border-radius: 4px; font-weight: bold; }
.badge-negative { background: #e25c73; color: #fff; padding: 2px 8px; border-radius: 4px; font-weight: bold; }
.heatmap td { background: linear-gradient(90deg, var(--bg) 0%, var(--bg) 100%); }
img { max-width: 100%; background: #fff1; border: 1px solid #2a2247; border-radius: 6px; }
.summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }
.card { background: #14122e; padding: 12px; border-radius: 8px; border: 1px solid #2a2247; }
.card .label { font-size: 10px; text-transform: uppercase; letter-spacing: 1px; color: #c9b88a; }
.card .value { font-size: 22px; font-weight: bold; margin-top: 4px; font-family: monospace; }
"""


def _heatmap_color(value: float, vmin: float, vmax: float) -> str:
    """value を vmin〜vmax で正規化して赤〜緑のグラデーション色を返す"""
    if vmax == vmin:
        return "#2a2247"
    t = (value - vmin) / (vmax - vmin)
    t = max(0.0, min(1.0, t))
    # 赤 (#e25c73) → 灰 → 緑 (#4ade80)
    if t < 0.5:
        # 赤→灰
        k = t * 2
        r = int(0xe2 * (1 - k) + 0x55 * k)
        g = int(0x5c * (1 - k) + 0x55 * k)
        b = int(0x73 * (1 - k) + 0x55 * k)
    else:
        k = (t - 0.5) * 2
        r = int(0x55 * (1 - k) + 0x4a * k)
        g = int(0x55 * (1 - k) + 0xde * k)
        b = int(0x55 * (1 - k) + 0x80 * k)
    return f"#{r:02x}{g:02x}{b:02x}"


def write_html(
    results: list[BacktestResult],
    stats_by_pm: dict,
    aggregate_by_method: dict,
    out_path: Path,
):
    """results: per (pair, method) の生データ。stats_by_pm: (pair, method) -> Stats。
    aggregate_by_method: method -> Stats (全ペア合算)
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    methods = sorted({r.method for r in results})
    pairs = sorted({r.pair for r in results})

    parts = []
    parts.append(f"<!doctype html><html><head><meta charset='utf-8'>")
    parts.append(f"<title>FX Signal Backtest Report</title>")
    parts.append(f"<style>{_CSS}</style></head><body>")
    parts.append("<h1>📊 FX Signal Monitor — Backtest Report</h1>")

    # ===== トップサマリ (手法別) =====
    parts.append("<div class='section'><h2>手法別サマリ (全ペア合算)</h2>")
    parts.append("<div class='summary'>")
    for m in methods:
        s = aggregate_by_method.get(m)
        if s is None:
            continue
        badge = ("badge-positive" if s.is_positive_ev else "badge-negative")
        label = "+EV" if s.is_positive_ev else "−EV"
        parts.append(f"""
        <div class='card'>
          <div class='label'>{m.upper()}</div>
          <div class='value'>{s.win_rate:.1f}%</div>
          <div style='font-size:11px'>勝率 ({s.wins}/{s.trades})</div>
          <div style='font-size:11px'>PF: <b>{s.profit_factor:.2f}</b></div>
          <div style='font-size:11px'>EV: <b>{s.expectancy_r:+.3f}R</b></div>
          <div style='font-size:11px'>累積: <b>{s.total_r:+.1f}R</b></div>
          <div style='font-size:11px'>最大DD: {s.max_dd_r:.1f}R</div>
          <div style='margin-top:4px'><span class='{badge}'>{label}</span></div>
        </div>
        """)
    parts.append("</div></div>")

    # ===== ペア × 手法 マトリックス (勝率) =====
    parts.append("<div class='section'><h2>ペア×手法 勝率マトリックス</h2>")
    parts.append("<table class='heatmap'><thead><tr><th>ペア \\ 手法</th>")
    for m in methods:
        parts.append(f"<th>{m.upper()}</th>")
    parts.append("</tr></thead><tbody>")
    # vmin/vmax を全体から決定
    all_wr = [s.win_rate for s in stats_by_pm.values() if s.trades > 0]
    vmin = min(all_wr) if all_wr else 0
    vmax = max(all_wr) if all_wr else 100
    for p in pairs:
        parts.append(f"<tr><td><b>{p}</b></td>")
        for m in methods:
            s = stats_by_pm.get((p, m))
            if s and s.trades > 0:
                color = _heatmap_color(s.win_rate, vmin, vmax)
                parts.append(
                    f"<td style='background:{color};color:#0b0a1f;font-weight:bold'>"
                    f"{s.win_rate:.0f}% ({s.trades})</td>"
                )
            else:
                parts.append("<td class='muted'>—</td>")
        parts.append("</tr>")
    parts.append("</tbody></table></div>")

    # ===== ペア × 手法 期待値 (R) =====
    parts.append("<div class='section'><h2>ペア×手法 期待値 (R / trade)</h2>")
    parts.append("<table class='heatmap'><thead><tr><th>ペア \\ 手法</th>")
    for m in methods:
        parts.append(f"<th>{m.upper()}</th>")
    parts.append("</tr></thead><tbody>")
    all_ev = [s.expectancy_r for s in stats_by_pm.values() if s.trades > 0]
    if all_ev:
        ev_min, ev_max = min(all_ev), max(all_ev)
    else:
        ev_min, ev_max = -1, 1
    for p in pairs:
        parts.append(f"<tr><td><b>{p}</b></td>")
        for m in methods:
            s = stats_by_pm.get((p, m))
            if s and s.trades > 0:
                color = _heatmap_color(s.expectancy_r, ev_min, ev_max)
                cls = "win" if s.expectancy_r > 0 else "loss"
                parts.append(
                    f"<td style='background:{color};color:#0b0a1f;font-weight:bold'>"
                    f"{s.expectancy_r:+.2f}</td>"
                )
            else:
                parts.append("<td class='muted'>—</td>")
        parts.append("</tr>")
    parts.append("</tbody></table></div>")

    # ===== 手法別 詳細 + Equity Curve =====
    parts.append("<div class='section'><h2>手法別エクイティカーブ (全ペア合算)</h2>")
    for m in methods:
        s = aggregate_by_method.get(m)
        if s is None or s.trades == 0:
            continue
        # この手法の全 trades を集める
        all_trades = []
        for r in results:
            if r.method == m:
                all_trades.extend(r.trades)
        all_trades.sort(key=lambda t: t.entry_time)
        img = _equity_chart(all_trades, f"{m.upper()} — total {s.total_r:+.1f}R over {s.trades} trades")
        if img:
            parts.append(f"<h3>{m.upper()}</h3>")
            parts.append(f"<img src='data:image/png;base64,{img}'/>")
            parts.append(f"<p>勝率: {s.win_rate:.1f}% | PF: {s.profit_factor:.2f} | "
                          f"EV: {s.expectancy_r:+.3f}R | MaxDD: {s.max_dd_r:.1f}R | "
                          f"連勝/連敗: {s.max_winstreak}/{s.max_lossstreak}</p>")
    parts.append("</div>")

    # ===== 全トレード詳細 =====
    parts.append("<div class='section'><h2>全トレード一覧 (上位 50 件)</h2>")
    all_trades = []
    for r in results:
        all_trades.extend(r.trades)
    all_trades.sort(key=lambda t: t.entry_time)
    parts.append("<table><thead><tr>"
                 "<th>#</th><th>ペア</th><th>手法</th><th>方向</th>"
                 "<th>Entry時刻</th><th>Entry価格</th><th>Exit時刻</th><th>Exit価格</th>"
                 "<th>理由</th><th>R</th><th>Pips</th></tr></thead><tbody>")
    for i, t in enumerate(all_trades[:50], 1):
        cls = "win" if (t.pnl_r or 0) > 0 else "loss"
        parts.append(
            f"<tr><td>{i}</td><td>{t.pair}</td><td>{t.method}</td><td>{t.direction}</td>"
            f"<td>{t.entry_time}</td><td>{t.entry_price:.5f}</td>"
            f"<td>{t.exit_time}</td><td>{(t.exit_price or 0):.5f}</td>"
            f"<td>{t.exit_reason}</td>"
            f"<td class='{cls}'>{(t.pnl_r or 0):+.2f}</td>"
            f"<td class='{cls}'>{(t.pnl_pips or 0):+.1f}</td></tr>"
        )
    parts.append("</tbody></table></div>")

    parts.append("<p class='muted' style='margin-top:48px;text-align:center'>Generated by fx-signal-monitor backtest engine</p>")
    parts.append("</body></html>")

    out_path.write_text("".join(parts), encoding="utf-8")
