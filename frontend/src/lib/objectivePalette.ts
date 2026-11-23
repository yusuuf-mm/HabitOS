/**
 * Fixed, colour-blind-safe objective palette shared by the life map and the
 * week calendar. Swatches are adapted from the Okabe–Ito palette: the eight
 * hues stay distinguishable under deuteranopia, protanopia and tritanopia.
 * Every objective also has a short code and a distinct shape, so colour is
 * never the only signal.
 *
 * The light/dark hex pairs below are mirrored by the CSS custom properties in
 * `index.css`. `objectivePalette.test.ts` asserts the two stay in sync and
 * checks every foreground/background pair against WCAG 2.2 contrast limits.
 */

export type ObjectiveShape =
  | "circle"
  | "square"
  | "diamond"
  | "triangle"
  | "hexagon"
  | "ring"
  | "cross"
  | "capsule";

export interface ObjectiveColors {
  swatch: string;
  ink: string;
  tint: string;
}

export interface ObjectiveStyle extends ObjectiveColors {
  key: string;
  label: string;
  short: string;
  shape: ObjectiveShape;
  light: ObjectiveColors;
  dark: ObjectiveColors;
}

function style(
  key: string,
  label: string,
  short: string,
  shape: ObjectiveShape,
  light: ObjectiveColors,
  dark: ObjectiveColors,
): ObjectiveStyle {
  return {
    key,
    label,
    short,
    shape,
    light,
    dark,
    swatch: `var(--objective-${key})`,
    ink: `var(--objective-${key}-ink)`,
    tint: `var(--objective-${key}-tint)`,
  };
}

export const OBJECTIVE_PALETTE: Record<string, ObjectiveStyle> = {
  health: style(
    "health",
    "Health",
    "HL",
    "circle",
    { swatch: "#0072B2", ink: "#005A8F", tint: "#E6F1F7" },
    { swatch: "#56B4E9", ink: "#A8DDFF", tint: "#102A3A" },
  ),
  productivity: style(
    "productivity",
    "Productivity",
    "PR",
    "square",
    { swatch: "#009E73", ink: "#006B4C", tint: "#E4F4EE" },
    { swatch: "#4FC09B", ink: "#7FE3C2", tint: "#0E2F27" },
  ),
  learning: style(
    "learning",
    "Learning",
    "LN",
    "diamond",
    { swatch: "#CC79A7", ink: "#8E3E67", tint: "#F7EAF2" },
    { swatch: "#E0A3C8", ink: "#F0B8DA", tint: "#321F2B" },
  ),
  wellness: style(
    "wellness",
    "Wellness",
    "WL",
    "triangle",
    { swatch: "#E69F00", ink: "#7A5000", tint: "#FBF1DE" },
    { swatch: "#F0B429", ink: "#FFD27F", tint: "#352A14" },
  ),
  social: style(
    "social",
    "Social",
    "SO",
    "hexagon",
    { swatch: "#D55E00", ink: "#9C4300", tint: "#FBEDE6" },
    { swatch: "#EF8B63", ink: "#FFB28C", tint: "#352018" },
  ),
  financial: style(
    "financial",
    "Financial",
    "FI",
    "ring",
    { swatch: "#56B4E9", ink: "#175E82", tint: "#E7F4FA" },
    { swatch: "#8ED4F5", ink: "#BEE9FF", tint: "#102B38" },
  ),
  creativity: style(
    "creativity",
    "Creativity",
    "CR",
    "cross",
    { swatch: "#F0E442", ink: "#6B5A00", tint: "#F8F4DA" },
    { swatch: "#F0E442", ink: "#F5E27A", tint: "#302C12" },
  ),
  mindfulness: style(
    "mindfulness",
    "Mindfulness",
    "MI",
    "capsule",
    { swatch: "#52525B", ink: "#27272A", tint: "#ECECEE" },
    { swatch: "#A1A1AA", ink: "#E4E4E7", tint: "#27272A" },
  ),
};

const FALLBACK_STYLES = Object.values(OBJECTIVE_PALETTE);

export const NEUTRAL_STYLE: ObjectiveStyle = {
  key: "neutral",
  label: "Unassigned",
  short: "—",
  shape: "capsule",
  swatch: "var(--objective-neutral)",
  ink: "var(--objective-neutral-ink)",
  tint: "var(--objective-neutral-tint)",
  light: { swatch: "#71717A", ink: "#3F3F46", tint: "#F1F1F2" },
  dark: { swatch: "#A1A1AA", ink: "#E4E4E7", tint: "#27272A" },
};

export function normalizeObjectiveName(name?: string | null): string {
  return (name ?? "").trim().toLowerCase();
}

function stableHash(value: string): number {
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash * 31 + value.charCodeAt(i)) >>> 0;
  }
  return hash;
}

/** Resolve any objective label to a fixed style, including unknown labels. */
export function resolveObjective(name?: string | null): ObjectiveStyle {
  const normalized = normalizeObjectiveName(name);
  if (!normalized) return NEUTRAL_STYLE;
  const known = OBJECTIVE_PALETTE[normalized];
  if (known) return known;
  return FALLBACK_STYLES[stableHash(normalized) % FALLBACK_STYLES.length];
}

export interface ObjectiveImpactLike {
  objectiveName?: string | null;
  impactScore?: number | null;
}

/**
 * A behaviour's main objective is the impact with the highest `impactScore`
 * stored in `objective_impacts` (-1..1), not the first row returned. Rows with
 * no usable score cannot establish a main objective. Ties break alphabetically
 * so the colour stays stable across requests.
 */
export function highestImpactObjective(
  impacts?: readonly ObjectiveImpactLike[] | null,
): ObjectiveImpactLike | undefined {
  if (!impacts?.length) return undefined;
  const usable = impacts.filter(
    (impact) => typeof impact.impactScore === "number" && Number.isFinite(impact.impactScore),
  );
  if (usable.length === 0) return undefined;
  return [...usable].sort((a, b) => {
    const delta = (b.impactScore ?? 0) - (a.impactScore ?? 0);
    if (delta !== 0) return delta;
    return (a.objectiveName ?? "").localeCompare(b.objectiveName ?? "");
  })[0];
}

function srgbChannel(channel: number): number {
  const value = channel / 255;
  return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
}

export function hexLuminance(hex: string): number {
  const value = hex.replace("#", "");
  const r = srgbChannel(parseInt(value.slice(0, 2), 16));
  const g = srgbChannel(parseInt(value.slice(2, 4), 16));
  const b = srgbChannel(parseInt(value.slice(4, 6), 16));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** WCAG 2.x contrast ratio between two six-digit hex colours. */
export function contrastRatio(a: string, b: string): number {
  const [lighter, darker] = [hexLuminance(a), hexLuminance(b)].sort((x, y) => y - x);
  return (lighter + 0.05) / (darker + 0.05);
}

export const ALL_OBJECTIVE_STYLES: readonly ObjectiveStyle[] = [
  ...Object.values(OBJECTIVE_PALETTE),
  NEUTRAL_STYLE,
];
