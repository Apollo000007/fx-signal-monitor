"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Bell, X } from "lucide-react";
import { useSignalsStore } from "@/store/signals";
import { cn } from "@/lib/utils";

export function ToastStack() {
  const { toasts, dismissToast, setSelected } = useSignalsStore();

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-3 pointer-events-none">
      <AnimatePresence>
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            layout
            initial={{ opacity: 0, x: 40, scale: 0.9 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: 40, scale: 0.9 }}
            transition={{ type: "spring", damping: 22, stiffness: 300 }}
            className={cn(
              "pointer-events-auto w-80 rounded-2xl glass p-4 shadow-glow cursor-pointer",
              "border-l-4",
              t.direction === "long" ? "border-accent-green" : "border-accent-red",
            )}
            onClick={() => {
              setSelected(t.pair);
              dismissToast(t.id);
            }}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2">
                <div
                  className={cn(
                    "h-8 w-8 rounded-full flex items-center justify-center",
                    t.direction === "long"
                      ? "bg-accent-green/15 text-accent-green"
                      : "bg-accent-red/15 text-accent-red",
                  )}
                >
                  <Bell className="h-4 w-4" />
                </div>
                <div>
                  <div className="font-mono font-semibold text-sm">{t.pair}</div>
                  <div className="text-[10px] text-text-dim uppercase tracking-wider">
                    {t.method === "orz"
                      ? "ORZ"
                      : t.method === "pdhl"
                        ? "PDH/PDL"
                        : t.method === "both"
                          ? "ORZ+PDHL"
                          : t.method === "claude"
                            ? "CLAUDE"
                            : "3手法合意"}
                    {" · "}
                    {t.direction === "long" ? "LONG トリガー" : "SHORT トリガー"}
                  </div>
                </div>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  dismissToast(t.id);
                }}
                className="text-text-faint hover:text-text"
                aria-label="dismiss"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="mt-3 flex items-baseline justify-between">
              <span className="text-[11px] text-text-dim">スコア</span>
              <span className="font-mono text-lg font-semibold accent-text">{t.score}</span>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
