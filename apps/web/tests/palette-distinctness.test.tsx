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
  return [channel(h + 1 / 3), channel(h), channel(h - 1 / 3)].map((c) => Math.round(c * 255)) as [number, number, number];
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
    const scale = (part: string) => part.endsWith("%") ? parseFloat(part) / 100 : parseFloat(part);
    const alpha = parts.length >= 4 ? (parts[3].endsWith("%") ? parseFloat(parts[3]) / 100 : parseFloat(parts[3])) : 1;
    if (!Number.isFinite(alpha)) return null;
    if (functional[1].startsWith("rgb")) {
      const channels = parts.slice(0, 3).map((part) => clamp(Math.round(part.endsWith("%") ? scale(part) * 255 : parseFloat(part)), 0, 255));
      if (!channels.every(Number.isFinite)) return null;
      return `rgba(${channels[0]}, ${channels[1]}, ${channels[2]}, ${clamp(alpha, 0, 1)})`;
    }
    // Hue may carry a unit: deg (default), turn, rad, grad, or a bare percent
    // (100% == 360deg). CSS folds it modulo 360; only then does hslToRgb see degrees.
    const huePart = parts[0];
    const hueUnits: Record<string, number> = { turn: 360, rad: 180 / Math.PI, grad: 360 / 400, deg: 1 };
    const unitMatch = /^(-?[\d.]+)(turn|rad|grad|deg|%)?$/.exec(huePart);
    const hue = unitMatch ? parseFloat(unitMatch[1]) * (unitMatch[2] === "%" ? 3.6 : hueUnits[unitMatch[2] ?? "deg"] ?? 1) : NaN;
    const [saturation, lightness] = [scale(parts[1]), scale(parts[2])];
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
