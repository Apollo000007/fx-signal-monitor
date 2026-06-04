"use client";

import { useEffect, useState } from "react";
import { TrendingUp, TrendingDown, Activity, Trophy } from "lucide-react";
import { fetchPaper, type PaperPayload, type PaperTrade } from "@/lib/paper";
import { cn } from "@/lib/utils";

const METHOD_LABEL: Record<string, string> = {
  orz: "ORZ",
  pdhl: "PDHL",
  both: "ORZ+PDHL",
  claude: "Claude",
  triple: "3 手法",
  dtp: "DTP 押し目",
  pa: "PA パターン",
  mtf: "MTF 全軸一致",
};

export function PaperStats() {
  const [data, setData] = useState<PaperPayload | null>(null);

  useEffect(() => {
    let aborted = false;
    const load = async () => {
      const p = await fetchPaper();
      if (!aborted) setData(p);
    };
    load();
    const id = window.setInterval(load, 60_000); // 1 分ごとに更新
    return () => {
      aborted = true;
      window.clearInterval(id);
    };
  }, []);

  if (!data || data.history_count === 0) {
    return (
      <div className="rounded-xl border border-border/60 bg-bg-soft/40 px-4 py-3 text-[11px] text-text-faint">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-text-dim" />
          <span className="font-semibold text-text-dim">PAPER TRADE</span>
          <span>累積戦績はトレード成立後に表示されます (まだ {data?.open_count ?? 0} ポジション open 中、履歴 0 件)</span>
        </div>
      </div>
    );
  }

  const s = data.stats;
  const ev_positive = s.expectancy_r > 0;
  const pf_color = s.profit_factor >= 1.5 ? "text-accent-green" : s.profit_factor >= 1.0 ? "text-accent-gold" : "text-accent-red";

  // 最強の手法を抽出
  const best_method = Object.entries(s.by_method)
    .filter(([, m]) => m.trades >= 5)
    .sort((a, b) => b[1].expectancy_r - a[1].expectancy_r)[0];

  return (
    <section className="rounded-2xl border border-accent-gold/30 bg-gradient-to-br from-accent-gold/5 via-bg-soft/40 to-accent-violet/5 p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-accent-gold animate-pulse-soft" />
          <span className="text-[11px] uppercase tracking-[0.2em] text-accent-gold font-serif font-semibold">
            Paper Trade · 累積戦績
          </span>
        </div>
        <span className="text-[10px] text-text-faint font-mono">
          {data.history_count} 件決済 / {data.open_count} オープン中
        </span>
      </div>

      {/* メイン指標 6 枚 */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
        <Stat label="勝率" value={`${s.win_rate.toFixed(1)}%`} sub={`${s.wins}勝 ${s.losses}敗`} />
        <Stat
          label="期待値"
          value={`${s.expectancy_r >= 0 ? "+" : ""}${s.expectancy_r.toFixed(3)}R`}
          color={ev_positive ? "text-accent-green" : "text-accent-red"}
          sub="/trade"
        />
        <Stat
          label="累積 R"
          value={`${s.total_r >= 0 ? "+" : ""}${s.total_r.toFixed(2)}R`}
          color={s.total_r >= 0 ? "text-accent-green" : "text-accent-red"}
        />
        <Stat
          label="PF"
          value={s.profit_factor >= 999 ? "∞" : s.profit_factor.toFixed(2)}
          color={pf_color}
          sub={s.profit_factor >= 1 ? "勝>負" : "負>勝"}
        />
        <Stat label="トレード数" value={`${s.trades}`} />
        <Stat
          label="最強手法"
          value={best_method ? METHOD_LABEL[best_method[0]] : "—"}
          color="text-accent-gold"
          sub={best_method ? `${best_method[1].expectancy_r >= 0 ? "+" : ""}${best_method[1].expectancy_r.toFixed(2)}R` : ""}
          icon={best_method ? <Trophy className="h-3 w-3" /> : undefined}
        />
      </div>

      {/* 手法別 mini ブレイクダウン */}
      {Object.keys(s.by_method).length > 0 && (
        <div className="mt-3 pt-3 border-t border-border/40">
          <div className="text-[9px] uppercase tracking-wider text-text-faint mb-1.5">手法別</div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 text-[10px]">
            {Object.entries(s.by_method).map(([m, st]) => (
              <div key={m} className="rounded-lg bg-bg-soft/40 border border-border/40 p-1.5">
                <div className="flex justify-between">
                  <span className="text-text-dim font-mono uppercase">{METHOD_LABEL[m] ?? m}</span>
                  <span className="text-text-faint">{st.trades}件</span>
                </div>
                <div className="flex justify-between mt-0.5">
                  <span className={cn(st.expectancy_r >= 0 ? "text-accent-green" : "text-accent-red", "font-mono")}>
                    {st.expectancy_r >= 0 ? "+" : ""}{st.expectancy_r.toFixed(2)}R
                  </span>
                  <span className="text-text-faint">{st.win_rate.toFixed(0)}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 最近 5 件 */}
      {data.recent_trades.length > 0 && (
        <div className="mt-3 pt-3 border-t border-border/40">
          <div className="text-[9px] uppercase tracking-wider text-text-faint mb-1.5">直近 5 件</div>
          <div className="space-y-1 text-[10px] font-mono">
            {data.recent_trades.slice(-5).reverse().map((t) => (
              <TradeRow key={t.id} t={t} />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function Stat({
  label, value, sub, color, icon,
}: {
  label: string;
  value: string;
  sub?: string;
  color?: string;
  icon?: React.ReactNode;
}) {
  return (
    <div className="rounded-lg bg-bg-soft/40 border border-border/40 px-2 py-1.5">
      <div className="text-[9px] uppercase tracking-wider text-text-faint flex items-center gap-1">
        {icon}{label}
      </div>
      <div className={cn("font-mono text-base font-bold mt-0.5", color ?? "text-text")}>
        {value}
      </div>
      {sub && <div className="text-[9px] text-text-faint">{sub}</div>}
    </div>
  );
}

function TradeRow({ t }: { t: PaperTrade }) {
  const profit = t.pnl_r > 0;
  return (
    <div className="flex items-center justify-between gap-2 px-2 py-1 rounded bg-bg-soft/40">
      <div className="flex items-center gap-2 min-w-0 flex-1">
        {profit ? (
          <TrendingUp className="h-3 w-3 text-accent-green shrink-0" />
        ) : (
          <TrendingDown className="h-3 w-3 text-accent-red shrink-0" />
        )}
        <span className="font-semibold truncate">{t.pair}</span>
        <span className="text-text-faint uppercase text-[9px]">{METHOD_LABEL[t.method] ?? t.method}</span>
        <span className={cn("text-[9px] uppercase", t.direction === "long" ? "text-accent-green" : "text-accent-red")}>
          {t.direction}
        </span>
      </div>
      <div className="flex gap-3 shrink-0">
        <span className="text-text-faint text-[9px] uppercase">{t.exit_reason}</span>
        <span className={cn("font-bold w-14 text-right", profit ? "text-accent-green" : "text-accent-red")}>
          {profit ? "+" : ""}{t.pnl_r.toFixed(2)}R
        </span>
        <span className={cn("w-16 text-right", profit ? "text-accent-green" : "text-accent-red")}>
          {profit ? "+" : ""}{t.pnl_pips.toFixed(1)}p
        </span>
      </div>
    </div>
  );
}
