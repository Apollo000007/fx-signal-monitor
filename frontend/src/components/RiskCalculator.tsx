"use client";

import { Calculator, Copy, Check } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { cn, formatPrice } from "@/lib/utils";
import type { Signal } from "@/lib/types";

interface Props {
  signal: Signal;
}

/**
 * 口座サイズとリスク% から推奨ロットを自動計算。
 *  - JPY クロス (例: USD/JPY) は pip = 0.01、それ以外は pip = 0.0001
 *  - pip 価値は 1 lot(= 10 万通貨) 当たり概算で
 *     JPY クロス: 1000 円 / pip
 *     それ以外   : 10 USD / pip  (必要なら USD/JPY でさらに換算するが、
 *                                ここでは簡易に JPY 建てに換算するために
 *                                現在値の USD/JPY が無いので 150 円で固定)
 *  - ユーザーが口座通貨 JPY 前提の想定
 *
 * SL 距離 (pips) = |entry - stop_loss| / pip_size
 * リスク額 (JPY) = account * risk%
 * pip 価値 / 1lot (JPY) = pipValuePerLot
 * 推奨ロット = リスク額 / (SL 距離 * pipValuePerLot)
 */
function isJpyCross(symbol: string): boolean {
  return /JPY$/i.test(symbol) || /JPY=X$/i.test(symbol);
}

const USDJPY_FALLBACK = 155; // USD/JPY が取れない場合の換算レート

export function RiskCalculator({ signal }: Props) {
  const [account, setAccount] = useState<number>(() => {
    if (typeof window === "undefined") return 1_000_000;
    const saved = Number(window.localStorage.getItem("fx_account_jpy"));
    return Number.isFinite(saved) && saved > 0 ? saved : 1_000_000;
  });
  const [riskPct, setRiskPct] = useState<number>(() => {
    if (typeof window === "undefined") return 1;
    const saved = Number(window.localStorage.getItem("fx_risk_pct"));
    return Number.isFinite(saved) && saved > 0 ? saved : 1;
  });
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem("fx_account_jpy", String(account));
  }, [account]);
  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem("fx_risk_pct", String(riskPct));
  }, [riskPct]);

  const calc = useMemo(() => {
    const { price, stop_loss, take_profit, symbol, pair } = signal;
    if (price == null || stop_loss == null) return null;
    const jpy = isJpyCross(symbol) || /JPY/i.test(pair);
    const pipSize = jpy ? 0.01 : 0.0001;
    const slPips = Math.abs(price - stop_loss) / pipSize;
    if (slPips <= 0) return null;
    const riskJpy = account * (riskPct / 100);
    // 1 lot = 100,000 通貨
    // JPY cross: 1 pip(=0.01) × 100_000 = 1000 JPY
    // それ以外: 1 pip(=0.0001) × 100_000 = 10 (base currency).
    //   USD 建てなら 10 USD → 10 × USDJPY JPY
    const pipValuePerLot = jpy ? 1000 : 10 * USDJPY_FALLBACK;
    const lots = riskJpy / (slPips * pipValuePerLot);
    const units = lots * 100_000;
    const tpPips = take_profit != null ? Math.abs(take_profit - price) / pipSize : null;
    const rr = tpPips != null ? tpPips / slPips : null;
    const expectedProfitJpy = tpPips != null ? tpPips * pipValuePerLot * lots : null;
    return {
      slPips,
      tpPips,
      riskJpy,
      lots,
      units,
      rr,
      expectedProfitJpy,
      jpy,
    };
  }, [account, riskPct, signal]);

  const copy = async () => {
    if (!calc) return;
    const text =
      `【${signal.pair} ${signal.direction.toUpperCase()}】\n` +
      `Entry: ${formatPrice(signal.price)}\n` +
      `SL   : ${formatPrice(signal.stop_loss)}  (-${calc.slPips.toFixed(1)} pips)\n` +
      `TP   : ${formatPrice(signal.take_profit)}` +
      (calc.tpPips != null ? `  (+${calc.tpPips.toFixed(1)} pips)` : "") + "\n" +
      (calc.rr != null ? `RR   : ${calc.rr.toFixed(2)}\n` : "") +
      `Lot  : ${calc.lots.toFixed(2)}  (≒ ${Math.round(calc.units).toLocaleString()} 通貨)\n` +
      `Risk : ${Math.round(calc.riskJpy).toLocaleString()} 円 (${riskPct}% of ${account.toLocaleString()})`;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <section className="rounded-xl border border-border/60 bg-bg-soft/40 p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 text-xs uppercase tracking-widest text-text-dim">
          <Calculator className="h-4 w-4 text-accent-cyan" />
          リスク計算機
        </div>
        <button
          onClick={copy}
          disabled={!calc}
          className={cn(
            "flex items-center gap-1.5 px-3 py-1 rounded-md text-[11px] font-semibold transition",
            "border border-border/60 bg-bg-card hover:bg-bg-hover",
            "disabled:opacity-40",
            copied && "text-accent-green border-accent-green/40 bg-accent-green/10",
          )}
        >
          {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
          {copied ? "コピー済" : "トレード条件をコピー"}
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-3">
        <label className="flex flex-col gap-1">
          <span className="text-[10px] text-text-faint uppercase tracking-wider">口座残高 (JPY)</span>
          <input
            type="number"
            value={account}
            onChange={(e) => setAccount(Math.max(0, Number(e.target.value) || 0))}
            className="px-2 py-1.5 rounded-md bg-bg-card border border-border/60 text-sm font-mono focus:border-accent-cyan/60 outline-none"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-[10px] text-text-faint uppercase tracking-wider">1トレードのリスク (%)</span>
          <input
            type="number"
            step="0.1"
            value={riskPct}
            onChange={(e) => setRiskPct(Math.max(0, Number(e.target.value) || 0))}
            className="px-2 py-1.5 rounded-md bg-bg-card border border-border/60 text-sm font-mono focus:border-accent-cyan/60 outline-none"
          />
        </label>
      </div>

      {calc ? (
        <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-[12px] font-mono">
          <Row k="SL 距離" v={`${calc.slPips.toFixed(1)} pips`} />
          <Row k="TP 距離" v={calc.tpPips != null ? `${calc.tpPips.toFixed(1)} pips` : "—"} />
          <Row k="リスク額" v={`${Math.round(calc.riskJpy).toLocaleString()} 円`} tone="red" />
          <Row k="想定利益" v={calc.expectedProfitJpy != null ? `${Math.round(calc.expectedProfitJpy).toLocaleString()} 円` : "—"} tone="green" />
          <Row k="推奨ロット" v={`${calc.lots.toFixed(2)} lot`} tone="accent" />
          <Row k="通貨数" v={`${Math.round(calc.units).toLocaleString()} 通貨`} />
          <Row k="RR 比率" v={calc.rr != null ? `1:${calc.rr.toFixed(2)}` : "—"} tone={calc.rr != null && calc.rr >= 2 ? "green" : "neutral"} />
          <Row k="基準 pip" v={calc.jpy ? "0.01 (JPY cross)" : "0.0001"} />
        </div>
      ) : (
        <div className="text-xs text-text-faint">SL/TP 未設定のため計算不可</div>
      )}
      <p className="mt-3 text-[10px] text-text-faint leading-relaxed">
        ※ 概算です。ブローカーの必要証拠金・手数料・スリッページは含みません。
        クロス円以外は USD/JPY = {USDJPY_FALLBACK} で換算しています。
      </p>
    </section>
  );
}

function Row({
  k,
  v,
  tone,
}: {
  k: string;
  v: string;
  tone?: "red" | "green" | "accent" | "neutral";
}) {
  const color =
    tone === "red"
      ? "text-accent-red"
      : tone === "green"
        ? "text-accent-green"
        : tone === "accent"
          ? "text-accent-cyan font-bold"
          : "text-text";
  return (
    <div className="flex justify-between">
      <span className="text-text-faint">{k}</span>
      <span className={color}>{v}</span>
    </div>
  );
}
