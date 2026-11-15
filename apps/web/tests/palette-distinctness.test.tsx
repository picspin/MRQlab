import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, it } from "vitest";
import { COLORS as MEASUREMENT_COLORS } from "../components/research/Measurements";
import { COLORS as TIMELINE_COLORS } from "../components/workbench/SequenceIRTimeline";

// Resolve a CSS custom property (or literal) through the token table, then
// normalize any color notation to one canonical RGBA string, so both a
// distinct-name alias (--cyan -> #70b8ff) and a cross-notation collision
// (#ff0000 vs rgb(255,0,0)) are caught rather than passing on spelling.
const styleCss = readFileSync(resolve(__dirname, "../app/style.css"), "utf8");
const tokens = new Map<string, string>();
const tokenPattern = /(--[a-z0-9-]+)\s*:\s*([^;]+);/g;
let tokenMatch: RegExpExecArray | null;
while ((tokenMatch = tokenPattern.exec(styleCss)) !== null) {
  tokens.set(tokenMatch[1], tokenMatch[2].trim());
}
function clamp(value: number, low: number, high: number): number {
  return Math.min(high, Math.max(low, value));
}
function hslToRgb(hue: number, saturation: number, lightness: number): [number, number, number] {
  const h = ((hue % 360) + 360) % 360 / 360;
  const q = lightness < 0.5 ? lightness * (1 + saturation) : lightness + saturation - lightness * saturation;
  const p = 2 * lightness - q;
  const channel = (t: number) => {
    const tt = ((t % 1) + 1) % 1;
    if (tt < 1 / 6) return p + (q - p) * 6 * tt;
    if (tt < 1 / 2) return q;
    if (tt < 2 / 3) return p + (q - p) * (2 / 3 - tt) * 6;
    return p;
  };
  // +1e-12 keeps a ramp value that is an exact .5 (e.g. 127.5 at hue 270, whose
  // double lands ~1.1e-13 short) from rounding down where CSS rounds up, while
  // staying far below the 0.5 tie so a hue just under a tie still rounds down.
  return [channel(h + 1 / 3), channel(h), channel(h - 1 / 3)].map((c) => Math.round(c * 255 + 1e-12)) as [number, number, number];
}
const NUMBER_SOURCE = "[+-]?(?:\\d+\\.?\\d*|\\.\\d+)(?:[eE][+-]?\\d+)?";
const NUMBER = new RegExp(`^(${NUMBER_SOURCE})(%?)$`);
const HUE = new RegExp(`^(${NUMBER_SOURCE})(turn|rad|grad|deg|%)?$`);
// Parse a CSS number token with an optional percent sign, or null if the token
// is malformed (e.g. "1.5.5"); a malformed token must not be truncated to a
// plausible value, matching how CSS drops the whole declaration.
function numeric(part: string): { value: number; percent: boolean } | null {
  const match = NUMBER.exec(part);
  return match ? { value: parseFloat(match[1]), percent: match[2] === "%" } : null;
}
function parseColor(input: string): string | null {
  const value = input.trim().toLowerCase();
  const hex = /^#([0-9a-f]{3,8})$/.exec(value);
  if (hex) {
    const digits = hex[1];
    const expand = (part: string) => parseInt(part.length === 1 ? part + part : part, 16);
    if (digits.length === 3 || digits.length === 4) {
      const [r, g, b] = [expand(digits[0]), expand(digits[1]), expand(digits[2])];
      const a = digits.length === 4 ? expand(digits[3]) / 255 : 1;
      return `rgba(${r}, ${g}, ${b}, ${a})`;
    }
    if (digits.length === 6 || digits.length === 8) {
      const [r, g, b] = [digits.slice(0, 2), digits.slice(2, 4), digits.slice(4, 6)].map(expand);
      const a = digits.length === 8 ? expand(digits.slice(6, 8)) / 255 : 1;
      return `rgba(${r}, ${g}, ${b}, ${a})`;
    }
    return null;
  }
  const functional = /^(rgba?|hsla?)\(([^)]+)\)$/.exec(value);
  if (functional) {
    const parts = functional[2].split(/[,\s/]+/).filter(Boolean);
    if (parts.length < 3) return null;
    // Every argument goes through the same number grammar, so a malformed token
    // (e.g. "1.5.5") drops the whole declaration instead of being truncated to a
    // plausible value by parseFloat. A unit-less s/l is a percentage in CSS.
    let alpha = 1;
    if (parts.length >= 4) {
      const token = numeric(parts[3]);
      if (!token) return null;
      alpha = token.percent ? token.value / 100 : token.value;
    }
    if (!Number.isFinite(alpha)) return null;
    if (functional[1].startsWith("rgb")) {
      const channels: number[] = [];
      for (const part of parts.slice(0, 3)) {
        const token = numeric(part);
        if (!token) return null;
        // A rgb channel is either a 0-255 number or a percentage of 255.
        channels.push(clamp(Math.round(token.percent ? (token.value / 100) * 255 : token.value), 0, 255));
      }
      return `rgba(${channels[0]}, ${channels[1]}, ${channels[2]}, ${clamp(alpha, 0, 1)})`;
    }
    // Hue may carry a unit: deg (default), turn, rad, grad, or a bare percent
    // (100% == 360deg). CSS folds it modulo 360; only then does hslToRgb see
    // degrees. The number grammar allows a sign, decimals, and an exponent.
    const hueUnits: Record<string, number> = { turn: 360, rad: 180 / Math.PI, grad: 360 / 400, deg: 1 };
    const unitMatch = HUE.exec(parts[0]);
    if (!unitMatch) return null;
    const hue = parseFloat(unitMatch[1]) * (unitMatch[2] === "%" ? 3.6 : hueUnits[unitMatch[2] ?? "deg"]);
    const saturationToken = numeric(parts[1]);
    const lightnessToken = numeric(parts[2]);
    if (!saturationToken || !lightnessToken) return null;
    const [saturation, lightness] = [saturationToken.value / 100, lightnessToken.value / 100];
    if (![hue, saturation, lightness].every(Number.isFinite)) return null;
    const [r, g, b] = hslToRgb(hue, clamp(saturation, 0, 1), clamp(lightness, 0, 1));
    return `rgba(${r}, ${g}, ${b}, ${clamp(alpha, 0, 1)})`;
  }
  return null;
}
function resolveColor(value: string, depth = 0): string {
  const alias = /^var\((--[a-z0-9-]+)\)$/.exec(value.trim());
  if (alias && depth < 8) {
    const target = tokens.get(alias[1]);
    if (target) return resolveColor(target, depth + 1);
  }
  return parseColor(value) ?? value.trim().toLowerCase();
}

it("normalizes equivalent CSS color notations to one value", () => {
  // #ff0000 and rgb(255,0,0) render identically; lowercasing the string alone
  // would treat them as two distinct colors and let a real collision pass.
  expect(resolveColor("#ff0000")).toBe(resolveColor("rgb(255,0,0)"));
  expect(resolveColor("#f00")).toBe(resolveColor("rgb(255, 0, 0)"));
  expect(resolveColor("rgba(255,0,0,0.5)")).toBe(resolveColor("rgb(255 0 0 / 50%)"));
});

it("clamps out-of-range channels and parses hue units like CSS", () => {
  // CSS clamps rgb() channels to [0,255] at parsed-value time, so rgb(300,0,0)
  // renders identically to #ff0000; an unclamped parse would hide that collision.
  expect(resolveColor("rgb(300,0,0)")).toBe(resolveColor("#ff0000"));
  expect(resolveColor("rgb(-40,0,0)")).toBe(resolveColor("#000000"));
  // A hue given in turn/rad/grad/percent must fold to degrees, not parse as a
  // bare number: 0.5turn is cyan, not red.
  expect(resolveColor("hsl(0.5turn, 100%, 50%)")).toBe(resolveColor("#00ffff"));
  expect(resolveColor("hsl(3.14159265rad, 100%, 50%)")).toBe(resolveColor("#00ffff"));
  expect(resolveColor("hsl(200grad, 100%, 50%)")).toBe(resolveColor("#00ffff"));
  expect(resolveColor("hsl(50%, 100%, 50%)")).toBe(resolveColor("#00ffff"));
});

it("parses the full CSS number grammar for hue and rejects malformed tokens", () => {
  // Exponent and explicit-sign hues are legal CSS numbers and render as their
  // numeric value; a dot-only character class would drop them to the raw string.
  expect(resolveColor("hsl(1e2, 100%, 50%)")).toBe(resolveColor("hsl(100, 100%, 50%)"));
  expect(resolveColor("hsl(+90, 100%, 50%)")).toBe(resolveColor("hsl(90, 100%, 50%)"));
  // A malformed token must be rejected, not silently truncated to a valid hue.
  expect(resolveColor("hsl(1.5.5turn, 100%, 50%)")).not.toBe(resolveColor("hsl(540, 100%, 50%)"));
});

it("treats bare hsl saturation/lightness as percentages and rounds like CSS", () => {
  // A unit-less s/l is a percentage in CSS, so hsl(0,50,50) == hsl(0,50%,50%).
  expect(resolveColor("hsl(0, 50, 50)")).toBe(resolveColor("hsl(0, 50%, 50%)"));
  // 270deg is exactly 127.5 in the red ramp; CSS rounds it up to 128, and the
  // float ramp must not fall one ulp short.
  expect(resolveColor("hsl(270, 100%, 50%)")).toBe(resolveColor("#8000ff"));
  // Pin the tie-rounding on a second, independent .5 boundary.
  expect(resolveColor("hsl(210, 100%, 50%)")).toBe(resolveColor("#0080ff"));
});

it("does not round a hue just below a .5 tie up, as CSS does not", () => {
  // 269.9999999999 deg is strictly below the 127.5 tie, so CSS rounds the red
  // channel down to 127 (#7f00ff); an over-wide epsilon would push it to 128.
  expect(resolveColor("hsl(269.9999999999, 100%, 50%)")).toBe(resolveColor("#7f00ff"));
});

it("rejects malformed hsl saturation/lightness like it rejects a malformed hue", () => {
  // A malformed s/l must not be silently truncated into a valid color; CSS
  // drops the whole declaration. Fall through to the raw string, not a color.
  expect(resolveColor("hsl(0, 1.5.5, 50)")).toBe("hsl(0, 1.5.5, 50)");
  expect(resolveColor("hsl(0, 50, 5e.5)")).toBe("hsl(0, 50, 5e.5)");
});

it("measurement curve palette resolves to four pairwise-distinct colors", () => {
  expect(MEASUREMENT_COLORS).toHaveLength(4);
  const resolved = MEASUREMENT_COLORS.map((color) => resolveColor(color));
  expect(new Set(resolved).size).toBe(MEASUREMENT_COLORS.length);
});

it("SequenceIR timeline channel palette resolves to pairwise-distinct colors", () => {
  const resolved = Object.values(TIMELINE_COLORS).map((color) => resolveColor(color));
  expect(new Set(resolved).size).toBe(resolved.length);
});

it("RF and Gz channels are distinguishable in the teaching timeline", () => {
  expect(resolveColor(TIMELINE_COLORS.rf_amp)).not.toBe(resolveColor(TIMELINE_COLORS.gz));
});
