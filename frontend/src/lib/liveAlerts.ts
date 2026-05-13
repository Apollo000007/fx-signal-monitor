/**
 * ライブ価格が「キーレベル」を跨いだ瞬間にブラウザ通知 + 音を鳴らす。
 *
 * キーレベル定義 (シグナルから抽出):
 *   - 前日高値 PDH / 前日安値 PDL
 *   - エントリー目安 (signal.price)
 *   - 損切り SL (signal.stop_loss)
 *   - 利確 TP (signal.take_profit)
 *
 * 同じレベル + 同じペア + 同じ方向のクロスは 5 分以内に再通知しない (debounce)。
 * これでスプレッド振動による連射を防ぐ。
 *
 * ブラウザ通知の権限取得は初回マウント時に Notification.requestPermission() で実施。
 */

import { useEffect, useRef } from "react";
import type { LivePrice } from "./oanda";
import type { Signal } from "./types";

type CrossDirection = "above" | "below";
type LevelKind = "PDH" | "PDL" | "Entry" | "SL" | "TP";

interface LevelDef {
  kind: LevelKind;
  price: number;
  /** ロング向け or ショート向け? — UI 表示用 */
  context?: "long" | "short" | "neutral";
}

interface CrossEvent {
  pair: string;
  symbol: string;
  kind: LevelKind;
  cross: CrossDirection;
  fromPrice: number;
  toPrice: number;
  level: number;
  at: number;
}

const COOLDOWN_MS = 5 * 60 * 1000; // 同一ペア+レベル+方向は 5 分

/** Notification 権限の取得 (ユーザージェスチャ不要、初回のみ) */
function ensurePermission(): void {
  if (typeof window === "undefined" || !("Notification" in window)) return;
  if (Notification.permission === "default") {
    Notification.requestPermission().catch(() => {
      /* ignore */
    });
  }
}

/** 短いビープ音を Web Audio で生成 */
function beep(freq = 880, ms = 140, volume = 0.08): void {
  if (typeof window === "undefined") return;
  try {
    const Ctx =
      (window as any).AudioContext ?? (window as any).webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.frequency.value = freq;
    osc.type = "sine";
    gain.gain.value = volume;
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + ms / 1000);
    setTimeout(() => ctx.close().catch(() => {}), ms + 200);
  } catch {
    /* ignore */
  }
}

function levelLabel(k: LevelKind): string {
  switch (k) {
    case "PDH":
      return "前日高値";
    case "PDL":
      return "前日安値";
    case "Entry":
      return "エントリー";
    case "SL":
      return "損切り";
    case "TP":
      return "利確";
  }
}

function notify(ev: CrossEvent): void {
  const dir = ev.cross === "above" ? "↑ 上抜け" : "↓ 下抜け";
  const title = `${ev.pair} ${dir} ${levelLabel(ev.kind)}`;
  const body =
    `${ev.fromPrice.toFixed(5)} → ${ev.toPrice.toFixed(5)}\n` +
    `レベル: ${ev.level.toFixed(5)}`;
  if (
    typeof window !== "undefined" &&
    "Notification" in window &&
    Notification.permission === "granted"
  ) {
    try {
      new Notification(title, {
        body,
        tag: `${ev.symbol}-${ev.kind}-${ev.cross}`,
        renotify: true,
      } as NotificationOptions);
    } catch {
      /* ignore */
    }
  }
  // 視覚的にも console に残す
  // eslint-disable-next-line no-console
  console.info(`[live-alert] ${title} — ${body}`);

  if (typeof window !== "undefined") {
    const direction = ev.cross === "above" ? "long" : "short";
    window.dispatchEvent(
      new CustomEvent("fx-impact-alert", {
        detail: {
          id: `live:${ev.symbol}:${ev.kind}:${ev.cross}:${ev.at}`,
          pair: ev.pair,
          direction,
          method: "LIVE LEVEL",
          triggerLabel: `${levelLabel(ev.kind)} ${dir} / ${ev.level.toFixed(5)}`,
          at: ev.at,
        },
      }),
    );
  }
}

function extractLevels(signal: Signal): LevelDef[] {
  const out: LevelDef[] = [];
  const ctx: "long" | "short" | "neutral" =
    signal.direction === "long" || signal.direction === "short"
      ? signal.direction
      : "neutral";
  if (signal.pdh != null) out.push({ kind: "PDH", price: signal.pdh, context: ctx });
  if (signal.pdl != null) out.push({ kind: "PDL", price: signal.pdl, context: ctx });
  if (signal.price != null && signal.direction !== "none") {
    out.push({ kind: "Entry", price: signal.price, context: ctx });
  }
  if (signal.stop_loss != null) out.push({ kind: "SL", price: signal.stop_loss, context: ctx });
  if (signal.take_profit != null) out.push({ kind: "TP", price: signal.take_profit, context: ctx });
  return out;
}

/**
 * 表示中の全シグナルとライブ価格 Map を渡すと、価格がキーレベルを跨いだ瞬間に通知。
 */
export function useLiveLevelAlerts(
  signals: Signal[],
  livePrices: Map<string, LivePrice>,
): void {
  // 直近価格を symbol ごとに保持 (前回値 → 今回値 のクロス判定用)
  const prevPriceRef = useRef<Map<string, number>>(new Map());
  // クールダウン管理: key = `${symbol}|${kind}|${cross}` → lastFiredAt
  const cooldownRef = useRef<Map<string, number>>(new Map());

  // 初回のみ通知許可を要求
  useEffect(() => {
    ensurePermission();
  }, []);

  // ライブ価格が更新されるたびにクロス判定
  useEffect(() => {
    const now = Date.now();
    for (const sig of signals) {
      const lp = livePrices.get(sig.symbol);
      if (!lp || lp.mid == null) continue;
      const cur = lp.mid;
      const prev = prevPriceRef.current.get(sig.symbol);
      if (prev == null || prev === cur) {
        prevPriceRef.current.set(sig.symbol, cur);
        continue;
      }

      const levels = extractLevels(sig);
      for (const lv of levels) {
        // cur と prev の間にレベルが挟まっているか
        const above = prev < lv.price && cur >= lv.price;
        const below = prev > lv.price && cur <= lv.price;
        if (!above && !below) continue;
        const cross: CrossDirection = above ? "above" : "below";

        const key = `${sig.symbol}|${lv.kind}|${cross}`;
        const last = cooldownRef.current.get(key) ?? 0;
        if (now - last < COOLDOWN_MS) continue;
        cooldownRef.current.set(key, now);

        // 通知 + 音
        notify({
          pair: sig.pair,
          symbol: sig.symbol,
          kind: lv.kind,
          cross,
          fromPrice: prev,
          toPrice: cur,
          level: lv.price,
          at: now,
        });
        // 上抜け = 高音 / 下抜け = 低音
        beep(cross === "above" ? 1320 : 660, 160);
      }
      prevPriceRef.current.set(sig.symbol, cur);
    }
    // signals 配列の identity / livePrices Map が変わるたびに評価する
  }, [signals, livePrices]);
}
