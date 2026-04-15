import clsx, { type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatPrice(value: number | null | undefined, digits = 4): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleTimeString("ja-JP", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function directionColor(dir: string): string {
  if (dir === "long") return "text-accent-green";
  if (dir === "short") return "text-accent-red";
  return "text-text-faint";
}

export function scoreColor(score: number): string {
  // すべて saturate 強め。グレー寄せは一切しない。
  if (score >= 85) return "from-emerald-400 via-cyan-300 to-sky-400";
  if (score >= 75) return "from-amber-300 via-lime-300 to-emerald-400";
  if (score >= 60) return "from-fuchsia-400 via-amber-300 to-lime-300";
  if (score >= 40) return "from-violet-500 via-fuchsia-400 to-amber-300";
  if (score >= 20) return "from-rose-500 via-orange-400 to-amber-300";
  return "from-rose-600 via-rose-500 to-orange-400";
}

export function scoreLabel(score: number, threshold = 75): {
  label: string;
  tone: "alert" | "warn" | "neutral" | "weak";
} {
  if (score >= threshold) return { label: "強い", tone: "alert" };
  if (score >= 60) return { label: "準備", tone: "warn" };
  if (score >= 40) return { label: "様子見", tone: "neutral" };
  return { label: "弱い", tone: "weak" };
}
