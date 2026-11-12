import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, it } from "vitest";
import { COLORS as MEASUREMENT_COLORS } from "../components/research/Measurements";
import { COLORS as TIMELINE_COLORS } from "../components/workbench/SequenceIRTimeline";

// Resolve a CSS custom property (or literal) to a lowercase hex/rgb string using
// the token table, so a distinct-name collision such as --cyan -> --blue-11 is
// caught rather than passing on the token spelling.
const styleCss = readFileSync(resolve(__dirname, "../app/style.css"), "utf8");
const tokens = new Map<string, string>();
const tokenPattern = /(--[a-z0-9-]+)\s*:\s*([^;]+);/g;
let tokenMatch: RegExpExecArray | null;
while ((tokenMatch = tokenPattern.exec(styleCss)) !== null) {
  tokens.set(tokenMatch[1], tokenMatch[2].trim());
}
function resolveColor(value: string, depth = 0): string {
  const alias = /^var\((--[a-z0-9-]+)\)$/.exec(value.trim());
  if (alias && depth < 8) {
    const target = tokens.get(alias[1]);
    if (target) return resolveColor(target, depth + 1);
  }
  return value.trim().toLowerCase();
}

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
