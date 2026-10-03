/**
 * The approved prototype's design system, as React Native values.
 * Four type sizes, each step at least 1.25x; one lime accent; severity carried
 * by tint plus hairline and always by its word, never by colour alone.
 */
export const color = {
  ink: "#0A0A0A", inkSoft: "#1C1C1A", ink3: "#3A3A36",
  muted: "#6B6B66", muted2: "#9A9A93",
  border: "#E4E4E0", border2: "#EFEFEC",
  surface: "#FAFAF8", surface2: "#F4F4F2", paper: "#FFFFFF", page: "#D7D7D3",
  lime: "#CDFF47", limeDeep: "#B4E824", limeWash: "#F2FFD0",
  danger: "#C2410C", dangerWash: "#FFF1E9", dangerLine: "#F3C9B1",
  warn: "#9A6700", warnWash: "#FFF8E3", warnLine: "#E8D6A0",
  wire: "#121210", wireText: "#E6E6E2", wireComment: "#8F8F88",
  ok: "#1F9D55",
} as const;

export const space = { s1: 4, s2: 8, s3: 12, s4: 16, s5: 24, s6: 32, s7: 48 } as const;
export const radius = { ctrl: 8, card: 16, panel: 28, pill: 999 } as const;
export const size = { xs: 11, sm: 14, md: 18, lg: 24 } as const;

export const font = {
  display: "BricolageGrotesque_700Bold",
  displayHeavy: "BricolageGrotesque_800ExtraBold",
  body: "IBMPlexSans_400Regular",
  bodyMedium: "IBMPlexSans_500Medium",
  bodySemi: "IBMPlexSans_600SemiBold",
  mono: "IBMPlexMono_400Regular",
  monoMedium: "IBMPlexMono_500Medium",
} as const;

export const severityStyle = {
  contraindicated: { bg: color.dangerWash, fg: color.danger, line: color.dangerLine },
  warning: { bg: color.warnWash, fg: color.warn, line: color.warnLine },
  monitor: { bg: color.surface2, fg: color.ink3, line: color.border },
} as const;

/** The wide-web layout (phone frame + explanation panel) starts here. */
export const WIDE = 980;
