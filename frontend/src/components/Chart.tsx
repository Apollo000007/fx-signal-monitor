"use client";

import { useEffect, useRef, useState } from "react";
import {
  ColorType,
  CrosshairMode,
  LineStyle,
  createChart,
  type IChartApi,
  type ISeriesApi,
} from "lightweight-charts";
import { getChart } from "@/lib/api";
import type { ChartResponse, ChartTf } from "@/lib/types";
import { cn } from "@/lib/utils";

export interface ChartLevels {
  pdh?: number | null;
  pdl?: number | null;
  resistances?: (number | null | undefined)[];
  supports?: (number | null | undefined)[];
  entry?: number | null;
  stopLoss?: number | null;
  takeProfit?: number | null;
}

interface Props {
  symbol: string;
  tf: "long" | "mid" | "short";
  height?: number;
  levels?: ChartLevels;
}

export function Chart({ symbol, tf, height = 420, levels }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const [data, setData] = useState<ChartResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let aborted = false;
    setLoading(true);
    setError(null);
    getChart(symbol, tf)
      .then((d) => {
        if (!aborted) setData(d);
      })
      .catch((e) => {
        if (!aborted) setError(String(e));
      })
      .finally(() => {
        if (!aborted) setLoading(false);
      });
    return () => {
      aborted = true;
    };
  }, [symbol, tf]);

  useEffect(() => {
    if (!containerRef.current || !data) return;

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#8a95b3",
        fontFamily: "ui-sans-serif, system-ui, 'Noto Sans JP'",
      },
      grid: {
        vertLines: { color: "rgba(138,149,179,0.08)" },
        horzLines: { color: "rgba(138,149,179,0.08)" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: {
        borderColor: "rgba(138,149,179,0.12)",
      },
      timeScale: {
        borderColor: "rgba(138,149,179,0.12)",
        timeVisible: true,
        secondsVisible: false,
      },
    });
    chartRef.current = chart;

    // Ichimoku cloud (two area series)
    const cloudA = chart.addAreaSeries({
      lineColor: "rgba(168,85,247,0)",
      topColor: "rgba(168,85,247,0.20)",
      bottomColor: "rgba(168,85,247,0.0)",
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    const cloudB = chart.addAreaSeries({
      lineColor: "rgba(34,211,238,0)",
      topColor: "rgba(34,211,238,0.15)",
      bottomColor: "rgba(34,211,238,0.0)",
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

    // Candles
    const candles = chart.addCandlestickSeries({
      upColor: "#10b981",
      downColor: "#f43f5e",
      wickUpColor: "#10b981",
      wickDownColor: "#f43f5e",
      borderVisible: false,
    });

    // SMAs
    const sma20 = chart.addLineSeries({
      color: "#22d3ee",
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    const sma50 = chart.addLineSeries({
      color: "#a855f7",
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    const sma100 = chart.addLineSeries({
      color: "#f59e0b",
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

    try {
      // Dedup by time just in case
      const byTime = new Map<number, typeof data.candles[number]>();
      for (const c of data.candles) byTime.set(c.time, c);
      const candleData = Array.from(byTime.values()).sort((a, b) => a.time - b.time);
      candles.setData(candleData as any);

      const dedupLine = (arr: { time: number; value: number }[]) => {
        const m = new Map<number, number>();
        for (const p of arr) m.set(p.time, p.value);
        return Array.from(m.entries())
          .sort((a, b) => a[0] - b[0])
          .map(([time, value]) => ({ time, value })) as any;
      };

      sma20.setData(dedupLine(data.sma20));
      sma50.setData(dedupLine(data.sma50));
      sma100.setData(dedupLine(data.sma100));
      cloudA.setData(dedupLine(data.senkou_a));
      cloudB.setData(dedupLine(data.senkou_b));

      // --- Horizontal price lines: PDH / PDL / S-R / entry / SL / TP ---
      if (levels) {
        const addLine = (
          price: number | null | undefined,
          color: string,
          title: string,
          style: LineStyle = LineStyle.Solid,
          width: 1 | 2 | 3 | 4 = 1,
        ) => {
          if (price == null || !Number.isFinite(price)) return;
          candles.createPriceLine({
            price,
            color,
            lineWidth: width,
            lineStyle: style,
            axisLabelVisible: true,
            title,
          });
        };

        addLine(levels.pdh, "#10b981", "PDH", LineStyle.Solid, 2);
        addLine(levels.pdl, "#f43f5e", "PDL", LineStyle.Solid, 2);

        (levels.resistances ?? []).slice(0, 3).forEach((r, i) =>
          addLine(r ?? null, "rgba(244,63,94,0.55)", `R${i + 1}`, LineStyle.Dashed, 1),
        );
        (levels.supports ?? []).slice(0, 3).forEach((s, i) =>
          addLine(s ?? null, "rgba(16,185,129,0.55)", `S${i + 1}`, LineStyle.Dashed, 1),
        );

        addLine(levels.entry, "#22d3ee", "Entry", LineStyle.Dotted, 2);
        addLine(levels.stopLoss, "#f43f5e", "SL", LineStyle.Solid, 1);
        addLine(levels.takeProfit, "#10b981", "TP", LineStyle.Solid, 1);
      }
    } catch (e) {
      console.error(e);
    }

    chart.timeScale().fitContent();

    const resize = () => {
      if (!containerRef.current) return;
      chart.applyOptions({ width: containerRef.current.clientWidth });
    };
    window.addEventListener("resize", resize);

    return () => {
      window.removeEventListener("resize", resize);
      chart.remove();
      chartRef.current = null;
    };
  }, [data, height, levels]);

  return (
    <div className="relative w-full">
      <div
        ref={containerRef}
        style={{ height }}
        className={cn("w-full rounded-lg overflow-hidden", loading && "opacity-30")}
      />
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="h-8 w-8 rounded-full border-2 border-accent-cyan/30 border-t-accent-cyan animate-spin" />
        </div>
      )}
      {error && (
        <div className="absolute inset-0 flex items-center justify-center text-accent-red text-sm">
          {error}
        </div>
      )}
      {/* Legend */}
      {data && (
        <div className="absolute top-2 left-2 flex flex-wrap gap-3 text-[11px] font-mono pointer-events-none">
          <LegendDot color="#22d3ee" label="SMA20" />
          <LegendDot color="#a855f7" label="SMA50" />
          <LegendDot color="#f59e0b" label="SMA100" />
          <LegendDot color="rgba(168,85,247,0.5)" label="Cloud" />
          {levels?.pdh != null && <LegendDot color="#10b981" label="PDH" />}
          {levels?.pdl != null && <LegendDot color="#f43f5e" label="PDL" />}
          {levels?.entry != null && <LegendDot color="#22d3ee" label="Entry" />}
        </div>
      )}
    </div>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-1.5 text-text-dim">
      <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
      {label}
    </div>
  );
}
