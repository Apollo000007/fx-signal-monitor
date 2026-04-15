import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  direction: "long" | "short" | "none" | string;
  isAlert?: boolean;
  hasTrigger?: boolean;
}

export function DirectionBadge({ direction, isAlert, hasTrigger }: Props) {
  if (direction === "long") {
    return (
      <span
        className={cn(
          "chip chip-long",
          isAlert && "ring-1 ring-accent-green/60 shadow-[0_0_20px_-5px] shadow-accent-green/50",
        )}
      >
        <TrendingUp className="h-3 w-3" />
        LONG
        {hasTrigger && <span className="ml-0.5">★</span>}
      </span>
    );
  }
  if (direction === "short") {
    return (
      <span
        className={cn(
          "chip chip-short",
          isAlert && "ring-1 ring-accent-red/60 shadow-[0_0_20px_-5px] shadow-accent-red/50",
        )}
      >
        <TrendingDown className="h-3 w-3" />
        SHORT
        {hasTrigger && <span className="ml-0.5">★</span>}
      </span>
    );
  }
  return (
    <span className="chip chip-none">
      <Minus className="h-3 w-3" />
      WAIT
    </span>
  );
}
