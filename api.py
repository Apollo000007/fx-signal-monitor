"""FastAPI バックエンド。既存の strategy モジュールをラップして REST API で公開。

エンドポイント:
  GET /api/health                     動作確認
  GET /api/pairs                      監視対象ペア一覧
  GET /api/signals                    全ペアの分析結果（スコア順）
  GET /api/chart/{symbol}?tf=mid      OHLC + SMA + Ichimoku を返す
  GET /api/config                     しきい値などの現在設定

tf は "long" / "mid" / "short" のいずれか。
"""
from __future__ import annotations

import asyncio
import math
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import config
from data_fetcher import fetch_all, fetch_multi
from indicators import ichimoku, sma
from strategy import analyze_pair
from strategy_claude import analyze_pair_claude
from strategy_pdhl import analyze_pair_pdhl

app = FastAPI(title="FX Signal API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- In-memory cache ----------------

_cache: dict[str, Any] = {
    "signals": None,
    "signals_at": None,
    "tf_data": {},  # (symbol, tf) -> (df, timestamp)
}
_cache_lock = asyncio.Lock()

SIGNAL_TTL = 120      # seconds
CHART_TTL = 120


def _clean_float(x):
    """NaN/Inf を JSON 安全な None に変換。"""
    if x is None:
        return None
    try:
        f = float(x)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _tf_to_dict(tf):
    if tf is None:
        return None
    return {
        "direction": tf.direction,
        "regime": getattr(tf, "regime", tf.direction),
        "clarity": int(getattr(tf, "clarity", 0) or 0),
        "close": _clean_float(tf.close),
        "sma20": _clean_float(tf.sma20),
        "sma50": _clean_float(tf.sma50),
        "sma100": _clean_float(tf.sma100),
        "slope20": _clean_float(getattr(tf, "slope20", 0.0)),
        "slope50": _clean_float(getattr(tf, "slope50", 0.0)),
        "slope100": _clean_float(getattr(tf, "slope100", 0.0)),
        "cloud_top": _clean_float(tf.cloud_top),
        "cloud_bottom": _clean_float(tf.cloud_bottom),
        "price_vs_cloud": tf.price_vs_cloud,
        "macd_hist": _clean_float(tf.macd_hist),
        "last_swing_high": _clean_float(tf.last_swing_high),
        "last_swing_low": _clean_float(tf.last_swing_low),
        "resistances": [_clean_float(x) for x in (tf.resistances or [])],
        "supports": [_clean_float(x) for x in (tf.supports or [])],
        "range_top": _clean_float(getattr(tf, "range_top", None)),
        "range_bottom": _clean_float(getattr(tf, "range_bottom", None)),
    }


def _orz_to_method_dict(sig) -> dict:
    """ORZ Signal → method sub-dict (Signal.orz)."""
    has_trigger = any(r.startswith("★") for r in sig.reasons)
    return {
        "direction": sig.direction,
        "entry_type": getattr(sig, "entry_type", "none"),
        "score": int(sig.score),
        "price": _clean_float(sig.price),
        "stop_loss": _clean_float(sig.stop_loss),
        "take_profit": _clean_float(sig.take_profit),
        "reasons": list(sig.reasons),
        "warnings": list(sig.warnings),
        "has_trigger": has_trigger,
        "is_alert": has_trigger and sig.score >= config.ALERT_THRESHOLD and sig.direction != "none",
    }


def _pdhl_to_method_dict(pdhl_dict: dict) -> dict:
    """strategy_pdhl の戻り値 → method sub-dict (Signal.pdhl)。"""
    return {
        "direction": pdhl_dict.get("direction", "none"),
        "entry_type": pdhl_dict.get("entry_type", "none"),
        "score": int(pdhl_dict.get("score", 0)),
        "price": _clean_float(pdhl_dict.get("price")),
        "stop_loss": _clean_float(pdhl_dict.get("stop_loss")),
        "take_profit": _clean_float(pdhl_dict.get("take_profit")),
        "reasons": list(pdhl_dict.get("reasons", [])),
        "warnings": list(pdhl_dict.get("warnings", [])),
        "has_trigger": bool(pdhl_dict.get("has_trigger", False)),
        "is_alert": bool(pdhl_dict.get("is_alert", False)),
        "pdh": _clean_float(pdhl_dict.get("pdh")),
        "pdl": _clean_float(pdhl_dict.get("pdl")),
    }


def _claude_to_method_dict(c: dict) -> dict:
    """strategy_claude の戻り値 → method sub-dict (Signal.claude)。"""
    return {
        "direction": c.get("direction", "none"),
        "entry_type": c.get("entry_type", "none"),
        "score": int(c.get("score", 0)),
        "price": _clean_float(c.get("price")),
        "stop_loss": _clean_float(c.get("stop_loss")),
        "take_profit": _clean_float(c.get("take_profit")),
        "reasons": list(c.get("reasons", [])),
        "warnings": list(c.get("warnings", [])),
        "has_trigger": bool(c.get("has_trigger", False)),
        "is_alert": bool(c.get("is_alert", False)),
    }


def _build_both_method(orz: dict, pdhl: dict) -> dict:
    """両手法が合意した場合だけアラートになるメソッド。

    合意条件:
      - direction が同じ (long or short)
      - 両者とも has_trigger
      - 両者のスコアが閾値以上
    """
    aligned = (
        orz["direction"] != "none"
        and orz["direction"] == pdhl["direction"]
    )
    both_trigger = orz["has_trigger"] and pdhl["has_trigger"]
    both_alert = orz["is_alert"] and pdhl["is_alert"]

    if not aligned:
        return {
            "direction": "none",
            "entry_type": "none",
            "score": 0,
            "price": orz["price"],
            "stop_loss": None,
            "take_profit": None,
            "reasons": ["両手法の方向不一致 → 見送り"],
            "warnings": [],
            "has_trigger": False,
            "is_alert": False,
        }

    # 平均スコアを代表値に
    avg_score = int(round((orz["score"] + pdhl["score"]) / 2))
    if both_alert:
        # 両方揃ったら少しボーナス
        avg_score = min(100, avg_score + 5)

    reasons = [
        f"両手法合意: {orz['direction'].upper()}",
        f"ORZ手法スコア: {orz['score']}/100 ({orz.get('entry_type','-')})",
        f"PDHL手法スコア: {pdhl['score']}/100 ({pdhl.get('entry_type','-')})",
    ]
    if both_trigger:
        reasons.append("★両手法とも15Mトリガー点灯")
    elif orz["has_trigger"]:
        reasons.append("ORZ側でトリガー点灯 (PDHL側はセットアップ段階)")
    elif pdhl["has_trigger"]:
        reasons.append("PDHL側でトリガー点灯 (ORZ側はセットアップ段階)")
    else:
        reasons.append("両手法ともトリガー未発火 (セットアップ待機)")

    # SL/TP は両手法のうちより保守的な側を採用
    def _tighter_sl(a, b, direction):
        vals = [v for v in (a, b) if v is not None]
        if not vals:
            return None
        return max(vals) if direction == "long" else min(vals)

    def _tighter_tp(a, b, direction):
        vals = [v for v in (a, b) if v is not None]
        if not vals:
            return None
        return min(vals) if direction == "long" else max(vals)

    return {
        "direction": orz["direction"],
        "entry_type": "both_confluence",
        "score": avg_score,
        "price": orz["price"],
        "stop_loss": _tighter_sl(orz["stop_loss"], pdhl["stop_loss"], orz["direction"]),
        "take_profit": _tighter_tp(orz["take_profit"], pdhl["take_profit"], orz["direction"]),
        "reasons": reasons,
        "warnings": list(set((orz.get("warnings") or []) + (pdhl.get("warnings") or []))),
        "has_trigger": both_trigger,
        "is_alert": both_alert,
    }


def _build_triple_method(orz: dict, pdhl: dict, claude: dict) -> dict:
    """3 手法 (ORZ + PDHL + Claude) が全て合意した場合のみアラートになる最上位メソッド。

    合意条件:
      - 3 手法すべてで direction が一致 (all long or all short)
      - 3 手法すべてで has_trigger == True
      - 3 手法すべてで is_alert == True
    """
    dirs = {orz["direction"], pdhl["direction"], claude["direction"]}
    aligned = (
        len(dirs) == 1
        and "none" not in dirs
    )
    all_trigger = orz["has_trigger"] and pdhl["has_trigger"] and claude["has_trigger"]
    all_alert = orz["is_alert"] and pdhl["is_alert"] and claude["is_alert"]

    if not aligned:
        return {
            "direction": "none",
            "entry_type": "none",
            "score": 0,
            "price": orz["price"],
            "stop_loss": None,
            "take_profit": None,
            "reasons": ["3 手法の方向不一致 → 見送り"],
            "warnings": [],
            "has_trigger": False,
            "is_alert": False,
        }

    direction = orz["direction"]
    avg_score = int(round((orz["score"] + pdhl["score"] + claude["score"]) / 3))
    if all_alert:
        avg_score = min(100, avg_score + 10)  # 3 手法合意は大きなボーナス

    reasons = [
        f"3 手法合意: {direction.upper()}",
        f"ORZ: {orz['score']}/100 ({orz.get('entry_type','-')})",
        f"PDHL: {pdhl['score']}/100 ({pdhl.get('entry_type','-')})",
        f"Claude: {claude['score']}/100 ({claude.get('entry_type','-')})",
    ]
    triggered_methods = [
        name for name, m in [("ORZ", orz), ("PDHL", pdhl), ("Claude", claude)]
        if m["has_trigger"]
    ]
    if len(triggered_methods) == 3:
        reasons.append("★ 3 手法すべてでトリガー点灯 (最高勝率ゾーン)")
    elif triggered_methods:
        reasons.append(
            f"トリガー発火中: {', '.join(triggered_methods)} "
            f"({3 - len(triggered_methods)} 手法が待機)"
        )
    else:
        reasons.append("3 手法ともセットアップ段階 (トリガー待機)")

    # SL/TP は 3 手法のうち最も保守的な値を採用
    def _tighter_sl(vals, direction):
        xs = [v for v in vals if v is not None]
        if not xs:
            return None
        return max(xs) if direction == "long" else min(xs)

    def _tighter_tp(vals, direction):
        xs = [v for v in vals if v is not None]
        if not xs:
            return None
        return min(xs) if direction == "long" else max(xs)

    warnings = list(set(
        (orz.get("warnings") or [])
        + (pdhl.get("warnings") or [])
        + (claude.get("warnings") or [])
    ))

    return {
        "direction": direction,
        "entry_type": "triple_confluence",
        "score": avg_score,
        "price": orz["price"],
        "stop_loss": _tighter_sl(
            [orz["stop_loss"], pdhl["stop_loss"], claude["stop_loss"]], direction
        ),
        "take_profit": _tighter_tp(
            [orz["take_profit"], pdhl["take_profit"], claude["take_profit"]], direction
        ),
        "reasons": reasons,
        "warnings": warnings,
        "has_trigger": all_trigger,
        "is_alert": all_alert,
    }


def _signal_to_dict(sig, pdhl_dict: dict, claude_dict: dict) -> dict:
    """Pair 全体のレコードを組み立て。5 メソッド分の sub-dict を持つ。"""
    orz = _orz_to_method_dict(sig)
    pdhl = _pdhl_to_method_dict(pdhl_dict)
    claude = _claude_to_method_dict(claude_dict)
    both = _build_both_method(orz, pdhl)
    triple = _build_triple_method(orz, pdhl, claude)
    return {
        "pair": sig.pair,
        "symbol": sig.symbol,
        "price": _clean_float(sig.price),
        # 全タブで使いたい共通メタ (前日高安 + トップレベルショートカット)
        "pdh": _clean_float(pdhl_dict.get("pdh")),
        "pdl": _clean_float(pdhl_dict.get("pdl")),
        "lt": _tf_to_dict(sig.lt),
        "mt": _tf_to_dict(sig.mt),
        "st": _tf_to_dict(sig.st),
        "orz": orz,
        "pdhl": pdhl,
        "claude": claude,
        "both": both,
        "triple": triple,
    }


def _compute_signals():
    pairs_items = list(config.PAIRS.items())
    symbols = [s for _, s in pairs_items]
    long_d, mid_d, short_d = fetch_all(
        symbols,
        config.LONG_INTERVAL, config.LONG_PERIOD, config.LONG_RESAMPLE,
        config.MID_INTERVAL, config.MID_PERIOD, config.MID_RESAMPLE,
        config.SHORT_INTERVAL, config.SHORT_PERIOD, config.SHORT_RESAMPLE,
    )

    # SMT 用の短期リターンコンテキスト (全ペア)
    pair_ctx: dict = {}
    for label, symbol in pairs_items:
        df_s = short_d.get(symbol)
        if df_s is None or len(df_s) < 8:
            continue
        try:
            recent = float(df_s["Close"].iloc[-1])
            base = float(df_s["Close"].iloc[-8])
            if base:
                pair_ctx[label] = (recent - base) / base * 100.0
        except Exception:
            pass

    results = []
    for label, symbol in pairs_items:
        try:
            sig = analyze_pair(
                label, symbol,
                long_d.get(symbol),
                mid_d.get(symbol),
                short_d.get(symbol),
            )
        except Exception as e:
            print(f"[api] analyze_pair({label}) error: {e}")
            from strategy import Signal as OrzSignal
            sig = OrzSignal(pair=label, symbol=symbol, direction="none",
                            reasons=[f"ORZ分析エラー: {e}"])
        try:
            pdhl = analyze_pair_pdhl(
                label, symbol,
                long_d.get(symbol),
                mid_d.get(symbol),
                short_d.get(symbol),
                all_pairs_context=pair_ctx,
                alert_threshold=config.ALERT_THRESHOLD,
            )
        except Exception as e:
            print(f"[api] analyze_pair_pdhl({label}) error: {e}")
            pdhl = {
                "pair": label, "symbol": symbol,
                "direction": "none", "entry_type": "none",
                "score": 0, "price": 0.0,
                "stop_loss": None, "take_profit": None,
                "reasons": [f"PDHL分析エラー: {e}"],
                "warnings": [], "has_trigger": False, "is_alert": False,
                "pdh": None, "pdl": None,
            }
        try:
            claude = analyze_pair_claude(
                label, symbol,
                long_d.get(symbol),
                mid_d.get(symbol),
                short_d.get(symbol),
                alert_threshold=config.ALERT_THRESHOLD,
            )
        except Exception as e:
            print(f"[api] analyze_pair_claude({label}) error: {e}")
            claude = {
                "pair": label, "symbol": symbol,
                "direction": "none", "entry_type": "none",
                "score": 0, "price": 0.0,
                "stop_loss": None, "take_profit": None,
                "reasons": [f"Claude分析エラー: {e}"],
                "warnings": [], "has_trigger": False, "is_alert": False,
            }
        results.append(_signal_to_dict(sig, pdhl, claude))
    # キャッシュにTF生データも保存しておく（チャート用）
    for _, symbol in pairs_items:
        _cache["tf_data"][(symbol, "long")] = (long_d.get(symbol), datetime.now(timezone.utc))
        _cache["tf_data"][(symbol, "mid")] = (mid_d.get(symbol), datetime.now(timezone.utc))
        _cache["tf_data"][(symbol, "short")] = (short_d.get(symbol), datetime.now(timezone.utc))
    # 先頭のソートはフロント側でメソッドごとに行うため、ここでは ORZ スコアで仮ソート。
    results.sort(key=lambda s: s["orz"]["score"], reverse=True)
    return results


@app.get("/api/health")
async def health():
    return {"ok": True, "time": datetime.now(timezone.utc).isoformat()}


@app.get("/api/config")
async def get_config():
    return {
        "alert_threshold": config.ALERT_THRESHOLD,
        "refresh_seconds": config.REFRESH_SECONDS,
        "long_label": config.LONG_LABEL,
        "mid_label": config.MID_LABEL,
        "short_label": config.SHORT_LABEL,
        "pair_count": len(config.PAIRS),
    }


@app.get("/api/pairs")
async def get_pairs():
    return [{"pair": p, "symbol": s} for p, s in config.PAIRS.items()]


@app.get("/api/signals")
async def get_signals(refresh: bool = False):
    async with _cache_lock:
        now = datetime.now(timezone.utc)
        cached = _cache["signals"]
        cached_at = _cache["signals_at"]
        if (
            not refresh
            and cached is not None
            and cached_at is not None
            and (now - cached_at).total_seconds() < SIGNAL_TTL
        ):
            return {"signals": cached, "updated_at": cached_at.isoformat(), "cached": True}

        loop = asyncio.get_running_loop()
        try:
            signals = await loop.run_in_executor(None, _compute_signals)
        except Exception as e:
            if cached is not None:
                return {"signals": cached, "updated_at": cached_at.isoformat(), "cached": True, "error": str(e)}
            raise HTTPException(status_code=500, detail=str(e))
        _cache["signals"] = signals
        _cache["signals_at"] = now
        return {"signals": signals, "updated_at": now.isoformat(), "cached": False}


def _df_to_candles(df: pd.DataFrame, max_bars: int = 300):
    """DataFrame を lightweight-charts 向けの配列に変換。"""
    if df is None or df.empty:
        return []
    df = df.tail(max_bars)
    candles = []
    for ts, row in df.iterrows():
        candles.append({
            "time": int(ts.timestamp()),
            "open": _clean_float(row["Open"]),
            "high": _clean_float(row["High"]),
            "low": _clean_float(row["Low"]),
            "close": _clean_float(row["Close"]),
        })
    return candles


def _series_to_line(df: pd.DataFrame, series: pd.Series, max_bars: int = 300):
    if df is None or df.empty:
        return []
    series = series.tail(max_bars)
    df_t = df.tail(max_bars)
    out = []
    for ts, val in zip(df_t.index, series.values):
        v = _clean_float(val)
        if v is None:
            continue
        out.append({"time": int(ts.timestamp()), "value": v})
    return out


@app.get("/api/chart/{symbol}")
async def get_chart(symbol: str, tf: str = Query("mid", pattern="^(long|mid|short)$")):
    key = (symbol, tf)
    now = datetime.now(timezone.utc)
    cached = _cache["tf_data"].get(key)
    df = None
    if cached is not None:
        df, cached_at = cached
        if (now - cached_at).total_seconds() > CHART_TTL:
            df = None

    if df is None:
        # まだキャッシュが無ければ個別フェッチ
        tf_map = {
            "long": (config.LONG_INTERVAL, config.LONG_PERIOD, config.LONG_RESAMPLE),
            "mid": (config.MID_INTERVAL, config.MID_PERIOD, config.MID_RESAMPLE),
            "short": (config.SHORT_INTERVAL, config.SHORT_PERIOD, config.SHORT_RESAMPLE),
        }
        iv, pr, rs = tf_map[tf]
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, fetch_multi, [symbol], iv, pr, rs)
        df = result.get(symbol)
        _cache["tf_data"][key] = (df, now)

    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {symbol}/{tf}")

    s20 = sma(df["Close"], 20)
    s50 = sma(df["Close"], 50)
    s100 = sma(df["Close"], 100)
    _, _, senkou_a, senkou_b = ichimoku(df["High"], df["Low"])

    return {
        "symbol": symbol,
        "tf": tf,
        "candles": _df_to_candles(df),
        "sma20": _series_to_line(df, s20),
        "sma50": _series_to_line(df, s50),
        "sma100": _series_to_line(df, s100),
        "senkou_a": _series_to_line(df, senkou_a),
        "senkou_b": _series_to_line(df, senkou_b),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
