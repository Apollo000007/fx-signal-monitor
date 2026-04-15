import { create } from "zustand";
import { getConfig, getSignals } from "@/lib/api";
import {
  projectSignal,
  type AppConfig,
  type Method,
  type PairRecord,
  type Signal,
} from "@/lib/types";

export type Filter = "all" | "long" | "short" | "alerts" | "pinned";
export type SortKey = "score" | "pair" | "direction";

// --- LocalStorage helpers --------------------------------------------------
const LS_SOUND = "fx_sound_enabled";
const LS_PINNED = "fx_pinned_pairs";
function lsBool(key: string, fallback: boolean): boolean {
  if (typeof window === "undefined") return fallback;
  const v = window.localStorage.getItem(key);
  if (v == null) return fallback;
  return v === "1";
}
function lsArr(key: string): string[] {
  if (typeof window === "undefined") return [];
  try {
    const v = window.localStorage.getItem(key);
    return v ? (JSON.parse(v) as string[]) : [];
  } catch {
    return [];
  }
}

// --- Alert beep (Web Audio API) -------------------------------------------
let audioCtx: AudioContext | null = null;
function beep(direction: "long" | "short") {
  if (typeof window === "undefined") return;
  try {
    audioCtx ??= new (window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
    const ctx = audioCtx;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    // long は高音 (880→1320 Hz 上昇)、short は低音 (660→440 Hz 下降)
    const [f1, f2] = direction === "long" ? [880, 1320] : [660, 440];
    osc.frequency.setValueAtTime(f1, ctx.currentTime);
    osc.frequency.linearRampToValueAtTime(f2, ctx.currentTime + 0.18);
    gain.gain.setValueAtTime(0.0001, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.25, ctx.currentTime + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.35);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.4);
  } catch (e) {
    console.warn("beep failed", e);
  }
}

interface Toast {
  id: string;
  pair: string;
  direction: "long" | "short";
  score: number;
  at: number;
  method: Method;
}

interface SignalsState {
  /** API から受け取った生データ (3 手法分を持つ)。 */
  records: PairRecord[];
  /** 現在選択されている手法タブ。 */
  method: Method;
  /** view-model: records を method で projection したもの。 */
  signals: Signal[];
  config: AppConfig | null;
  loading: boolean;
  updatedAt: string | null;
  error: string | null;
  selected: string | null;
  filter: Filter;
  sortKey: SortKey;
  search: string;
  pinned: string[];
  toasts: Toast[];
  soundEnabled: boolean;
  /** method ごとの『通知済みアラートキー』。 */
  _seenAlertKeys: Record<Method, Set<string>>;

  fetchConfig: () => Promise<void>;
  refresh: (force?: boolean) => Promise<void>;
  setSelected: (pair: string | null) => void;
  setFilter: (f: Filter) => void;
  setSortKey: (k: SortKey) => void;
  setSearch: (s: string) => void;
  setMethod: (m: Method) => void;
  togglePin: (pair: string) => void;
  dismissToast: (id: string) => void;
  toggleSound: () => void;
}

function projectAll(records: PairRecord[], method: Method): Signal[] {
  return records.map((r) => projectSignal(r, method));
}

export const useSignalsStore = create<SignalsState>((set, get) => ({
  records: [],
  method: "orz",
  signals: [],
  config: null,
  loading: false,
  updatedAt: null,
  error: null,
  selected: null,
  filter: "all",
  sortKey: "score",
  search: "",
  pinned: lsArr(LS_PINNED),
  toasts: [],
  soundEnabled: lsBool(LS_SOUND, true),
  _seenAlertKeys: {
    orz: new Set<string>(),
    pdhl: new Set<string>(),
    both: new Set<string>(),
    claude: new Set<string>(),
    triple: new Set<string>(),
  },

  fetchConfig: async () => {
    try {
      const cfg = await getConfig();
      set({ config: cfg });
    } catch (e) {
      set({ error: String(e) });
    }
  },

  refresh: async (force = false) => {
    set({ loading: true, error: null });
    try {
      const res = await getSignals(force);
      const records = res.signals as unknown as PairRecord[];
      const method = get().method;
      const signals = projectAll(records, method);

      // 新アラート検出 — 現在アクティブな手法のみトースト表示
      const seen = get()._seenAlertKeys;
      const prev = seen[method];
      const nextPrev = new Set<string>(prev);
      const newToasts: Toast[] = [];
      for (const s of signals) {
        if (s.is_alert && s.direction !== "none") {
          const key = `${s.pair}:${s.direction}`;
          if (!prev.has(key)) {
            newToasts.push({
              id: `${method}:${key}:${Date.now()}`,
              pair: s.pair,
              direction: s.direction,
              score: s.score,
              at: Date.now(),
              method,
            });
            nextPrev.add(key);
          }
        }
      }

      set({
        records,
        signals,
        updatedAt: res.updated_at,
        loading: false,
        toasts: [...get().toasts, ...newToasts],
        _seenAlertKeys: { ...seen, [method]: nextPrev },
      });

      // 音で通知
      if (get().soundEnabled && newToasts.length > 0) {
        // 複数同時アラートは 200ms 間隔で順番に鳴らす
        newToasts.forEach((t, i) => {
          setTimeout(() => beep(t.direction), i * 220);
        });
      }

      for (const t of newToasts) {
        setTimeout(() => {
          set((st) => ({ toasts: st.toasts.filter((x) => x.id !== t.id) }));
        }, 8000);
      }
    } catch (e) {
      set({ error: String(e), loading: false });
    }
  },

  setSelected: (pair) => set({ selected: pair }),
  setFilter: (filter) => set({ filter }),
  setSortKey: (sortKey) => set({ sortKey }),
  setSearch: (search) => set({ search }),

  setMethod: (method) => {
    // タブ切替時に records を新 method で projection し直す
    const records = get().records;
    set({
      method,
      signals: projectAll(records, method),
    });
  },

  togglePin: (pair) =>
    set((st) => {
      const pinned = st.pinned.includes(pair)
        ? st.pinned.filter((p) => p !== pair)
        : [...st.pinned, pair];
      if (typeof window !== "undefined") {
        window.localStorage.setItem(LS_PINNED, JSON.stringify(pinned));
      }
      return { pinned };
    }),

  dismissToast: (id) =>
    set((st) => ({ toasts: st.toasts.filter((t) => t.id !== id) })),

  toggleSound: () =>
    set((st) => {
      const next = !st.soundEnabled;
      if (typeof window !== "undefined") {
        window.localStorage.setItem(LS_SOUND, next ? "1" : "0");
      }
      return { soundEnabled: next };
    }),
}));

export function selectFilteredSignals(state: SignalsState): Signal[] {
  let list = [...state.signals];

  if (state.filter === "long") list = list.filter((s) => s.direction === "long");
  else if (state.filter === "short") list = list.filter((s) => s.direction === "short");
  else if (state.filter === "alerts") list = list.filter((s) => s.is_alert);
  else if (state.filter === "pinned") list = list.filter((s) => state.pinned.includes(s.pair));

  if (state.search.trim()) {
    const q = state.search.trim().toLowerCase();
    list = list.filter(
      (s) => s.pair.toLowerCase().includes(q) || s.symbol.toLowerCase().includes(q),
    );
  }

  const pinned = state.pinned;
  const key = state.sortKey;
  list.sort((a, b) => {
    const pa = pinned.includes(a.pair) ? 0 : 1;
    const pb = pinned.includes(b.pair) ? 0 : 1;
    if (pa !== pb) return pa - pb;
    if (key === "score") return b.score - a.score;
    if (key === "pair") return a.pair.localeCompare(b.pair);
    if (key === "direction") return a.direction.localeCompare(b.direction);
    return 0;
  });

  return list;
}
