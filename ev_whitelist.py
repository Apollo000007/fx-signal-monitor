"""手法×ペアの +EV ホワイトリスト (全手法共通ゲート)。

2週間デモの所見: DTP が非推奨ペア(EUR/USD等)で多発し負けた。
「過去データで +EV と実証されたペアだけ alert する」を全手法に強制する。

- state/ev_whitelist.json を mtime キャッシュで読む (strategy_pa._load_whitelist 踏襲)。
  形式: {"min_n":20,"min_pf":1.1,"entries":{"triple|AUD/JPY":{n,wr,pf,ev}, ...}}
- 生成は scripts/backtest.py --emit-whitelist。
- 未生成/エントリ不在時の既定 (ブートストラップ):
    triple → 開 (唯一明確に +EV だった実績)
    dtp    → 既知の4ペアのみ (AUD/JPY,NZD/USD,USD/CHF,GBP/JPY)
    pdhl/orz → 閉 (1:1 / 不安定TP のため降格)
    pa     → ここでは判定しない (strategy_pa が pair×pattern で自己ゲート)
- is_alert の最終ゲートとして api._signal_to_dict から呼ぶ。これで signals.json
  自体が +EV のみ alert になり、Telegram/paper/MT5/UI が自動追従する。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WHITELIST_FILE = ROOT / "state" / "ev_whitelist.json"

# ブートストラップ既定 (ホワイトリスト未生成時)
_DTP_DEFAULT_PAIRS = {"AUD/JPY", "NZD/USD", "USD/CHF", "GBP/JPY"}
_OPEN_DEFAULT = {"triple"}        # 既定で全ペア許可
_CLOSED_DEFAULT = {"pdhl", "orz", "both", "claude"}  # 既定で全ペア不許可 (降格)

_cache: dict = {"mtime": None, "data": None}


def _load() -> dict | None:
    try:
        st = WHITELIST_FILE.stat()
    except OSError:
        return None
    if _cache["mtime"] != st.st_mtime:
        try:
            _cache["data"] = json.loads(WHITELIST_FILE.read_text(encoding="utf-8"))
            _cache["mtime"] = st.st_mtime
        except Exception:
            return None
    return _cache["data"]


def is_pair_allowed(method: str, pair: str) -> tuple[bool, str]:
    """(method, pair) が +EV ホワイトリストで alert 許可か。

    Returns: (allowed, reason_text)

    ゲート設計 (2週間デモの所見＋60日バックテストに基づく):
      - pa     : strategy_pa が pair×pattern で自己ゲート → 常に素通し。
      - triple : 3手法合議そのものが EV ゲート。低頻度・高精度 (60d で全ペア +EV、
                 ただし各ペア n<20) のため**ペア別 n≥20 を課さず常に許可**。
      - dtp    : 「生成された whitelist」∪「証拠ベースの4ペア」で許可。
                 4ペア(AUD/JPY,NZD/USD,USD/CHF,GBP/JPY)は先行研究で +EV 実証済の
                 床。短い検証窓で n<20 でも落とさない。whitelist は追加促進のみ。
      - pdhl/orz/both/claude : whitelist 掲載時のみ許可 (既定は閉=降格)。
    """
    if method == "pa":
        return True, ""  # PA は pair×pattern で自己判定
    if method == "triple":
        return True, "TRIPLE 3手法合議 (常時許可・合議が EV ゲート)"

    wl = _load()
    entries = (wl or {}).get("entries", {})
    in_wl = f"{method}|{pair}" in entries

    if method == "dtp":
        if in_wl:
            e = entries[f"{method}|{pair}"]
            return True, (f"DTP EV実証済 ({pair}: n={e.get('n')} "
                          f"WR{e.get('wr')}% PF{e.get('pf')} EV{e.get('ev')}R)")
        if pair in _DTP_DEFAULT_PAIRS:
            return True, f"DTP 証拠ベース推奨ペア {pair} (4ペア床)"
        return False, f"DTP 非推奨ペア {pair} — アラート保留"

    # pdhl / orz / both / claude: whitelist 掲載時のみ許可
    if in_wl:
        e = entries[f"{method}|{pair}"]
        return True, (f"EV実証済 ({method} {pair}: n={e.get('n')} "
                      f"WR{e.get('wr')}% PF{e.get('pf')} EV{e.get('ev')}R)")
    return False, f"{method} {pair} は +EV 未実証 — アラート保留 (降格手法)"
