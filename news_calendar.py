"""FX 経済カレンダー取得 + 当日相場リスクスコア算出。

データ源: Forex Factory 無料週間フィード (API キー不要)。
  https://nfs.faireconomy.media/ff_calendar_thisweek.json
各イベント: title / country(=通貨コード) / date(ISO+offset) / impact / forecast / previous

cron (GitHub Actions, クリーン IP) から呼ばれ、
frontend/public/api/calendar.json を書き出す想定。
フロントは signals.json と同様に静的読み込みする。

注意: ここは「表示・通知の付加情報」。strategy*.py / api.py の
シグナル本体 (アラート判定・バックテスト) には一切関与しない。
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

import requests

try:
    from zoneinfo import ZoneInfo
    _JST = ZoneInfo("Asia/Tokyo")
except Exception:  # tzdata 不在環境のフォールバック
    _JST = timezone(timedelta(hours=9))

import config

FEED_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# 監視通貨ペアに登場する通貨コード集合 (USD/JPY → {USD, JPY} ...)
def _monitored_currencies() -> set[str]:
    cur: set[str] = set()
    for disp in config.PAIRS:
        for code in disp.split("/"):
            cur.add(code.strip().upper())
    return cur


# 特大イベント判定キーワード (小文字 title 部分一致)
_MARQUEE_KW = (
    "non-farm", "nonfarm", "fomc", "federal funds rate", "cpi",
    "core pce", "interest rate decision", "official cash rate",
    "monetary policy", "rate statement", "press conference",
    "unemployment rate", "gdp", "powell", "fed chair", "boj",
    "ecb ", "boe ", "rba ", "snb ", "tankan",
)

_IMPACT_WEIGHT = {"High": 3, "Medium": 1, "Low": 0, "Holiday": 0}


def _fetch_raw() -> Optional[list[dict]]:
    try:
        r = requests.get(FEED_URL, headers={"User-Agent": _UA}, timeout=15)
        if r.status_code != 200:
            print(f"[calendar] feed status {r.status_code}")
            return None
        data = r.json()
        return data if isinstance(data, list) else None
    except Exception as e:
        print(f"[calendar] fetch error: {e}")
        return None


def _parse_dt(s: str) -> Optional[datetime]:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _stars_from_score(score: int, has_marquee: bool) -> tuple[int, str, str]:
    """score → (stars 1-5, level ラベル, tone)"""
    if score <= 0:
        stars, level, tone = 1, "平時", "calm"
    elif score <= 2:
        stars, level, tone = 2, "やや注意", "calm"
    elif score <= 5:
        stars, level, tone = 3, "注意", "watch"
    elif score <= 9:
        stars, level, tone = 4, "警戒", "warn"
    else:
        stars, level, tone = 5, "高警戒", "high"
    if has_marquee and stars < 4:
        stars, level, tone = 4, "警戒 (重要指標あり)", "warn"
    return stars, level, tone


def build_calendar_payload(now: Optional[datetime] = None) -> dict:
    """calendar.json に書き出す payload を組み立てる。

    フェッチ失敗時は events=[] / risk 不明の最小 payload を返す
    (呼び出し側で前回キャッシュにフォールバックする)。
    """
    now = now or datetime.now(timezone.utc)
    now_jst = now.astimezone(_JST)
    today_jst = now_jst.date()
    monitored = _monitored_currencies()

    raw = _fetch_raw()
    if raw is None:
        return {
            "updated_at": now.isoformat(),
            "tz": "Asia/Tokyo",
            "today": today_jst.isoformat(),
            "ok": False,
            "risk": {
                "score": 0, "stars": 1, "level": "データ取得待ち",
                "tone": "calm", "summary": "経済カレンダーを取得できませんでした",
                "headline_events": [],
            },
            "events": [],
        }

    events: list[dict] = []
    today_score = 0
    has_marquee_today = False
    headline: list[dict] = []

    for ev in raw:
        country = str(ev.get("country", "")).strip().upper()
        if country not in monitored:
            continue
        dt = _parse_dt(str(ev.get("date", "")))
        if dt is None:
            continue
        jst = dt.astimezone(_JST)
        impact = str(ev.get("impact", "")).strip() or "Low"
        title = str(ev.get("title", "")).strip()
        is_today = jst.date() == today_jst
        is_marquee = any(kw in title.lower() for kw in _MARQUEE_KW)

        events.append({
            "id": f"{country}-{jst.isoformat()}-{title[:32]}",
            "currency": country,
            "impact": impact,
            "title": title,
            "forecast": str(ev.get("forecast", "") or ""),
            "previous": str(ev.get("previous", "") or ""),
            "jst_iso": jst.isoformat(),
            "jst_date": jst.date().isoformat(),
            "jst_time": jst.strftime("%H:%M"),
            "is_today": is_today,
            "is_marquee": is_marquee,
        })

        if is_today:
            today_score += _IMPACT_WEIGHT.get(impact, 0)
            if is_marquee and impact in ("High", "Medium"):
                has_marquee_today = True
            if impact == "High":
                headline.append({
                    "currency": country,
                    "title": title,
                    "jst_time": jst.strftime("%H:%M"),
                })

    events.sort(key=lambda e: e["jst_iso"])
    headline.sort(key=lambda h: h["jst_time"])

    stars, level, tone = _stars_from_score(today_score, has_marquee_today)
    n_high = sum(1 for e in events if e["is_today"] and e["impact"] == "High")
    n_mid = sum(1 for e in events if e["is_today"] and e["impact"] == "Medium")
    summary = (
        f"本日 重要度 高 {n_high} 件 / 中 {n_mid} 件"
        + ("・重要指標あり" if has_marquee_today else "")
        if (n_high or n_mid) else "本日は主要な経済指標の予定が少なめです"
    )

    return {
        "updated_at": now.isoformat(),
        "tz": "Asia/Tokyo",
        "today": today_jst.isoformat(),
        "ok": True,
        "risk": {
            "score": today_score,
            "stars": stars,
            "level": level,
            "tone": tone,
            "summary": summary,
            "headline_events": headline[:6],
        },
        "events": events,
    }


if __name__ == "__main__":  # 手動デバッグ用
    import json
    print(json.dumps(build_calendar_payload(), ensure_ascii=False, indent=2)[:4000])
