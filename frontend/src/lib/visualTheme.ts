export type VisualTheme = "eva" | "olympus";

export const activeVisualTheme: VisualTheme =
  process.env.NEXT_PUBLIC_FX_VISUAL_THEME === "olympus" ? "olympus" : "eva";

export const isEvaTheme = activeVisualTheme === "eva";
