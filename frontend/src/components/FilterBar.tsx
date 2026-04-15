"use client";

import { Search, RefreshCw, Zap, TrendingUp, TrendingDown, List, Pin } from "lucide-react";
import { cn } from "@/lib/utils";
import { useSignalsStore, type Filter, type SortKey } from "@/store/signals";

export function FilterBar() {
  const {
    filter,
    setFilter,
    sortKey,
    setSortKey,
    search,
    setSearch,
    refresh,
    loading,
  } = useSignalsStore();

  return (
    <div className="flex flex-wrap items-center gap-3 p-3 glass rounded-2xl">
      <div className="relative flex-1 min-w-[180px]">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-faint" />
        <input
          data-search
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="ペアを検索 ( / キーでフォーカス)"
          className="w-full pl-9 pr-3 py-2 rounded-lg bg-bg-soft border border-border/60 focus:border-accent-gold/60 outline-none text-sm font-mono placeholder:text-text-faint"
        />
      </div>

      <div className="flex items-center gap-1 p-1 rounded-lg bg-bg-soft border border-border/60">
        <FilterBtn active={filter === "all"} onClick={() => setFilter("all")} icon={<List className="h-3.5 w-3.5" />}>
          全て
        </FilterBtn>
        <FilterBtn
          active={filter === "long"}
          onClick={() => setFilter("long")}
          icon={<TrendingUp className="h-3.5 w-3.5" />}
          color="green"
        >
          LONG
        </FilterBtn>
        <FilterBtn
          active={filter === "short"}
          onClick={() => setFilter("short")}
          icon={<TrendingDown className="h-3.5 w-3.5" />}
          color="red"
        >
          SHORT
        </FilterBtn>
        <FilterBtn
          active={filter === "alerts"}
          onClick={() => setFilter("alerts")}
          icon={<Zap className="h-3.5 w-3.5" />}
          color="amber"
        >
          アラート
        </FilterBtn>
        <FilterBtn
          active={filter === "pinned"}
          onClick={() => setFilter("pinned")}
          icon={<Pin className="h-3.5 w-3.5" />}
        >
          ピン
        </FilterBtn>
      </div>

      <select
        value={sortKey}
        onChange={(e) => setSortKey(e.target.value as SortKey)}
        className="px-3 py-2 rounded-lg bg-bg-soft border border-border/60 text-sm outline-none focus:border-accent-gold/60"
      >
        <option value="score">スコア順</option>
        <option value="pair">ペア名順</option>
        <option value="direction">方向順</option>
      </select>

      <button
        onClick={() => refresh(true)}
        disabled={loading}
        className={cn(
          "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold",
          "bg-accent-gradient text-white shadow-glow",
          "disabled:opacity-50 transition",
        )}
      >
        <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
        更新
      </button>
    </div>
  );
}

function FilterBtn({
  children,
  active,
  onClick,
  icon,
  color,
}: {
  children: React.ReactNode;
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  color?: "green" | "red" | "amber";
}) {
  const colorMap = {
    green: "data-[active=true]:text-accent-green data-[active=true]:bg-accent-green/10",
    red: "data-[active=true]:text-accent-red data-[active=true]:bg-accent-red/10",
    amber: "data-[active=true]:text-accent-amber data-[active=true]:bg-accent-amber/10",
  };
  return (
    <button
      data-active={active}
      onClick={onClick}
      className={cn(
        "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition",
        "text-text-dim hover:text-text",
        "data-[active=true]:bg-bg-card data-[active=true]:text-text",
        color && colorMap[color],
      )}
    >
      {icon}
      {children}
    </button>
  );
}
