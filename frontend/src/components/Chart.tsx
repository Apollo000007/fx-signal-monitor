"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Maximize2, Minimize2, Minus, Plus, RotateCcw } from "lucide-react";
import {
  ColorType,
  CrosshairMode,
  LineStyle,
  createChart,
  type IChartApi,
  type IPriceLine,
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
  /** メイン利確: 最低 2R (構造 TP が 2R より遠ければそれを採用)。RR 1:2 → 勝率33%でブレークイーブン */
  takeProfit?: number | null;
  /** 資産管理: 3R 利確 (リスクリワード 1:3 — 勝率25%でも資産増、プロ推奨) */
  mmTp3R?: number | null;
}

interface Props {
  symbol: string;
  tf: ChartTf;
  /** 固定高 (px)。fillParent=true の場合は無視され、親要素の高さに追従する */
  height?: number;
  /** true で親要素の高さに自動追従 (フルスクリーン表示用) */
  fillParent?: boolean;
  /** フルスクリーン切替ボタンを表示する場合のハンドラ */
  onToggleFullscreen?: () => void;
  /** 現在フルスクリーン状態か (ボタンアイコンの切替に使用) */
  isFullscreen?: boolean;
  levels?: ChartLevels;
  /** ライブ価格 (mid)。1 分ごとに更新される金色の水平線として描画 (チャート全体は再生成しない) */
  liveMid?: number | null;
}

/** TF ごとのローディング表示 (m1/m5 は yfinance のレスポンスが遅い) */
const TF_LOADING_HINT: Record<string, string> = {
  m1: "1分足: 7日分のデータを取得中… (10〜20秒)",
  m5: "5分足: 30日分のデータを取得中… (5〜10秒)",
  h1: "1時間足: データ取得中…",
  short: "15分足: データ取得中…",
  mid: "4時間足: データ取得中…",
  long: "日足: データ取得中…",
  week: "週足: データ取得中…",
};

const TF_LABEL: Record<string, string> = {
  m1: "1M", m5: "5M", short: "15M", h1: "1H", mid: "4H", long: "日足", week: "週足",
};

function readChartPalette() {
  const styles = getComputedStyle(document.documentElement);
  const color = (name: string, fallback: string) =>
    styles.getPropertyValue(name).trim() || fallback;
  return {
    text: color("--chart-text", "#c9b88a"),
    grid: color("--chart-grid", "rgba(168,85,247,0.06)"),
    axis: color("--chart-axis", "rgba(168,85,247,0.18)"),
    crosshair: color("--chart-crosshair", "rgba(233,196,106,0.4)"),
    labelBg: color("--chart-label-bg", "#1a1636"),
    up: color("--chart-up", "#10b981"),
    down: color("--chart-down", "#f43f5e"),
    sma20: color("--chart-sma20", "#22d3ee"),
    sma50: color("--chart-sma50", "#a855f7"),
    sma100: color("--chart-sma100", "#f59e0b"),
    cloudA: color("--chart-cloud-a", "rgba(168,85,247,0.20)"),
    cloudB: color("--chart-cloud-b", "rgba(34,211,238,0.15)"),
  };
}

export function Chart({
  symbol,
  tf,
  height = 420,
  fillParent = false,
  onToggleFullscreen,
  isFullscreen = false,
  levels,
  liveMid,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  // ローソク本体への参照。LIVE 価格ラインを後付け / 差し替えするのに使う。
  const candlesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const livePriceLineRef = useRef<IPriceLine | null>(null);
  const [data, setData] = useState<ChartResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);

  const handleZoomIn = useCallback(() => {
    const ts = chartRef.current?.timeScale();
    if (!ts) return;
    const range = ts.getVisibleLogicalRange();
    if (!range) return;
    const span = range.to - range.from;
    const newSpan = Math.max(span * 0.6, 5);
    ts.setVisibleLogicalRange({ from: range.to - newSpan, to: range.to });
  }, []);

  const handleZoomOut = useCallback(() => {
    const ts = chartRef.current?.timeScale();
    if (!ts) return;
    const range = ts.getVisibleLogicalRange();
    if (!range) return;
    const span = range.to - range.from;
    const newSpan = span * 1.6;
    ts.setVisibleLogicalRange({ from: range.to - newSpan, to: range.to });
  }, []);

  const handleFit = useCallback(() => {
    chartRef.current?.timeScale().fitContent();
  }, []);

  useEffect(() => {
    let aborted = false;
    setLoading(true);
    setError(null);
    setElapsedMs(0);
    const startedAt = performance.now();
    const tick = window.setInterval(() => {
      if (!aborted) setElapsedMs(performance.now() - startedAt);
    }, 200);
    getChart(symbol, tf)
      .then((d) => {
        if (!aborted) setData(d);
      })
      .catch((e) => {
        if (!aborted) setError(String(e));
      })
      .finally(() => {
        if (!aborted) setLoading(false);
        window.clearInterval(tick);
      });
    return () => {
      aborted = true;
      window.clearInterval(tick);
    };
  }, [symbol, tf]);

  useEffect(() => {
    if (!containerRef.current || !data) return;
    const palette = readChartPalette();

    const initialWidth = containerRef.current.clientWidth;
    const initialHeight = fillParent
      ? containerRef.current.clientHeight || height
      : height;

    const chart = createChart(containerRef.current, {
      width: initialWidth,
      height: initialHeight,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: palette.text,
        fontFamily: "var(--font-sans), ui-sans-serif, system-ui, 'Noto Sans JP'",
        fontSize: 12,
      },
      grid: {
        vertLines: { color: palette.grid },
        horzLines: { color: palette.grid },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          color: palette.crosshair,
          width: 1,
          style: LineStyle.Dashed,
          labelBackgroundColor: palette.labelBg,
        },
        horzLine: {
          color: palette.crosshair,
          width: 1,
          style: LineStyle.Dashed,
          labelBackgroundColor: palette.labelBg,
        },
      },
      rightPriceScale: {
        borderColor: palette.axis,
        scaleMargins: { top: 0.08, bottom: 0.08 },
      },
      timeScale: {
        borderColor: palette.axis,
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 8,
        barSpacing: 8,
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: true,
      },
      handleScale: {
        axisPressedMouseMove: true,
        mouseWheel: true,
        pinch: true,
      },
    });
    chartRef.current = chart;

    // Ichimoku cloud (two area series)
    const cloudA = chart.addAreaSeries({
      lineColor: "rgba(168,85,247,0)",
      topColor: palette.cloudA,
      bottomColor: "rgba(168,85,247,0.0)",
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    const cloudB = chart.addAreaSeries({
      lineColor: "rgba(34,211,238,0)",
      topColor: palette.cloudB,
      bottomColor: "rgba(34,211,238,0.0)",
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

    // Candles
    const candles = chart.addCandlestickSeries({
      upColor: palette.up,
      downColor: palette.down,
      wickUpColor: palette.up,
      wickDownColor: palette.down,
      borderVisible: false,
    });
    candlesRef.current = candles;
    // 前回の LIVE 価格ライン参照は無効化 (チャート再生成のため)
    livePriceLineRef.current = null;

    // SMAs
    const sma20 = chart.addLineSeries({
      color: palette.sma20,
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    const sma50 = chart.addLineSeries({
      color: palette.sma50,
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    const sma100 = chart.addLineSeries({
      color: palette.sma100,
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

        addLine(levels.pdh, palette.up, "前日高値", LineStyle.Solid, 2);
        addLine(levels.pdl, palette.down, "前日安値", LineStyle.Solid, 2);

        (levels.resistances ?? []).slice(0, 3).forEach((r, i) =>
          addLine(r ?? null, palette.down, `レジ${i + 1}`, LineStyle.Dashed, 1),
        );
        (levels.supports ?? []).slice(0, 3).forEach((s, i) =>
          addLine(s ?? null, palette.up, `サポ${i + 1}`, LineStyle.Dashed, 1),
        );

        addLine(levels.entry, palette.sma20, "エントリー", LineStyle.Dotted, 2);
        // --- 資産管理ライン: 1R = |entry - SL|. メイン利確 = 最低2R (勝率33%でBE),
        //     推奨 = 3R (勝率25%でも資産増)。1:1 の構造TPはここでは描画しない ---
        addLine(levels.stopLoss, palette.down, "損切り (1R)", LineStyle.Solid, 2);
        addLine(levels.takeProfit, palette.up, "利確 最低2R", LineStyle.Solid, 2);
        addLine(levels.mmTp3R, palette.crosshair, "利確 推奨3R", LineStyle.Solid, 3);
        // ※ LIVE 現在値ラインは別 useEffect (liveMid 変化のみで更新、チャート再生成なし) で管理
      }
    } catch (e) {
      console.error(e);
    }

    chart.timeScale().fitContent();

    let ro: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined" && containerRef.current) {
      ro = new ResizeObserver((entries) => {
        for (const entry of entries) {
          const w = Math.floor(entry.contentRect.width);
          const h = Math.floor(entry.contentRect.height);
          if (w <= 0) continue;
          if (fillParent && h > 0) {
            chart.applyOptions({ width: w, height: h });
          } else {
            chart.applyOptions({ width: w });
          }
        }
      });
      ro.observe(containerRef.current);
    }

    const resize = () => {
      if (!containerRef.current) return;
      chart.applyOptions({ width: containerRef.current.clientWidth });
    };
    window.addEventListener("resize", resize);

    return () => {
      ro?.disconnect();
      window.removeEventListener("resize", resize);
      chart.remove();
      chartRef.current = null;
      candlesRef.current = null;
      livePriceLineRef.current = null;
    };
  }, [data, height, fillParent, levels]);

  // --- LIVE 価格ライン (1 分ごとの更新でチャート全体は再生成しない) ---
  useEffect(() => {
    const series = candlesRef.current;
    if (!series) return;
    // 既存のラインを除去
    if (livePriceLineRef.current) {
      try {
        series.removePriceLine(livePriceLineRef.current);
      } catch {
        /* チャート破棄後の競合は無視 */
      }
      livePriceLineRef.current = null;
    }
    // 新しい値で再作成
    if (liveMid != null && Number.isFinite(liveMid)) {
      try {
        livePriceLineRef.current = series.createPriceLine({
          price: liveMid,
          color: "#e9c46a",
          lineWidth: 2,
          lineStyle: LineStyle.Solid,
          axisLabelVisible: true,
          title: "★ LIVE",
        });
      } catch {
        /* チャート破棄直後など */
      }
    }
  }, [liveMid, data]);

  return (
    <div className={cn("relative w-full", fillParent && "h-full")}>
      <div
        ref={containerRef}
        style={fillParent ? undefined : { height }}
        className={cn(
          "w-full rounded-lg overflow-hidden",
          fillParent && "h-full",
          loading && "opacity-30",
        )}
      />
      {loading && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 px-4 text-center">
          <div className="h-8 w-8 rounded-full border-2 border-accent-cyan/30 border-t-accent-cyan animate-spin" />
          <div className="text-[11px] font-mono text-text-dim">
            {TF_LOADING_HINT[tf] ?? "データ取得中…"}
          </div>
          <div className="text-[10px] font-mono text-text-faint">
            {TF_LABEL[tf] ?? tf} · {(elapsedMs / 1000).toFixed(1)}s
          </div>
          {elapsedMs > 8000 && (
            <div className="text-[10px] text-accent-amber/80 max-w-xs">
              データソース (yfinance) のレスポンスが遅延しています。しばらくお待ちください…
            </div>
          )}
        </div>
      )}
      {error && (
        <div className="absolute inset-0 flex items-center justify-center text-accent-red text-sm">
          {error}
        </div>
      )}
      {/* Legend — 日本語で一目でわかる凡例カード */}
      {data && (
        <div className="absolute top-2 left-2 max-w-[calc(100%-7rem)] rounded-lg border border-border/60 bg-bg-card/85 backdrop-blur-sm px-2.5 py-2 pointer-events-none shadow-card">
          <div className="text-[10px] uppercase tracking-wider text-text-faint mb-1">凡例</div>
          <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px]">
            <LegendItem swatch="line" color="var(--chart-sma20)" label="SMA20" />
            <LegendItem swatch="line" color="var(--chart-sma50)" label="SMA50" />
            <LegendItem swatch="dashed" color="var(--chart-sma100)" label="SMA100" />
            <LegendItem swatch="cloud" color="var(--chart-sma50)" label="一目雲" />
            {levels?.pdh != null && (
              <LegendItem swatch="solid" color="var(--chart-up)" label="前日高値" />
            )}
            {levels?.pdl != null && (
              <LegendItem swatch="solid" color="var(--chart-down)" label="前日安値" />
            )}
            {(levels?.resistances?.some((r) => r != null) ?? false) && (
              <LegendItem swatch="dashed" color="var(--chart-down)" label="レジスタンス" />
            )}
            {(levels?.supports?.some((s) => s != null) ?? false) && (
              <LegendItem swatch="dashed" color="var(--chart-up)" label="サポート" />
            )}
            {levels?.entry != null && (
              <LegendItem swatch="dotted" color="var(--chart-sma20)" label="エントリー" />
            )}
            {levels?.stopLoss != null && (
              <LegendItem swatch="solid" color="var(--chart-down)" label="損切り (1R)" />
            )}
            {levels?.takeProfit != null && (
              <LegendItem swatch="solid" color="var(--chart-up)" label="利確 最低2R" />
            )}
            {levels?.mmTp3R != null && (
              <LegendItem swatch="solid" color="var(--chart-crosshair)" label="利確 推奨3R" />
            )}
          </div>
        </div>
      )}
      {/* Zoom + fullscreen controls */}
      {data && (
        <div className="absolute top-2 right-2 flex flex-col gap-1.5">
          <ChartCtrlBtn onClick={handleZoomIn} title="ズームイン">
            <Plus className="h-3.5 w-3.5" />
          </ChartCtrlBtn>
          <ChartCtrlBtn onClick={handleZoomOut} title="ズームアウト">
            <Minus className="h-3.5 w-3.5" />
          </ChartCtrlBtn>
          <ChartCtrlBtn onClick={handleFit} title="全体表示にリセット">
            <RotateCcw className="h-3.5 w-3.5" />
          </ChartCtrlBtn>
          {onToggleFullscreen && (
            <ChartCtrlBtn
              onClick={onToggleFullscreen}
              title={isFullscreen ? "全画面を終了 (Esc)" : "全画面表示"}
            >
              {isFullscreen ? (
                <Minimize2 className="h-3.5 w-3.5" />
              ) : (
                <Maximize2 className="h-3.5 w-3.5" />
              )}
            </ChartCtrlBtn>
          )}
        </div>
      )}
    </div>
  );
}

function ChartCtrlBtn({
  onClick,
  title,
  children,
}: {
  onClick: () => void;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-label={title}
      className="rounded-md p-1.5 bg-bg-card/85 backdrop-blur-sm border border-border/60 text-text-dim hover:text-accent-gold hover:bg-bg-hover hover:border-accent-gold/50 transition shadow-sm"
    >
      {children}
    </button>
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

/** ライン種別を視覚的に表現する凡例。実線/破線/点線/雲 を区別する */
function LegendItem({
  swatch,
  color,
  label,
}: {
  swatch: "line" | "solid" | "dashed" | "dotted" | "cloud";
  color: string;
  label: string;
}) {
  return (
    <div className="flex items-center gap-1.5 text-text-dim">
      <span className="inline-flex items-center justify-center w-5 h-3">
        {swatch === "cloud" ? (
          <span
            className="block w-4 h-2 rounded-sm"
            style={{ backgroundColor: color, opacity: 0.4 }}
          />
        ) : (
          <span
            className="block w-4 h-0"
            style={{
              borderTopWidth: 2,
              borderTopStyle:
                swatch === "dashed" ? "dashed" : swatch === "dotted" ? "dotted" : "solid",
              borderTopColor: color,
            }}
          />
        )}
      </span>
      <span className="text-text">{label}</span>
    </div>
  );
}
