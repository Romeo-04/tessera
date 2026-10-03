import scenario from "../demo/scenario.json";
import type { Ambiguity, Drug, SessionResult } from "./types";

const RXCUI = /^RXCUI:\d+$/;

/**
 * The browser side of the privacy gate. The same allowlist as
 * src/tessera/privacy.py and the API's request schema: three independent
 * checks, so a bug in any one of them is not a leak.
 */
export function codeSetFor(codes: string[]): { codes: string[] } {
  for (const c of codes) {
    if (!RXCUI.test(c)) throw new Error(`refusing to transmit ${JSON.stringify(c)}`);
  }
  return { codes: [...new Set(codes)].sort() };
}

/**
 * Re-attach names to a codes-only answer. The server never had the names; the
 * browser had them all along. A code we cannot name stays unnamed — an
 * unnamed code is better than an invented name.
 */
export function rejoinNames(result: SessionResult, drugs: Drug[]): SessionResult {
  const names = new Map<string, string>();
  for (const d of drugs) if (d.rxcui && d.display_name) names.set(d.rxcui, d.display_name);
  return {
    ...result,
    risks: result.risks.map((r) => ({
      ...r,
      subject_name: names.get(r.subject) ?? null,
      object_name: names.get(r.object) ?? null,
    })),
  };
}

interface DemoDrug extends Drug {
  options?: Ambiguity["options"];
  margin?: number;
  ingredient_rxcui?: string;
  directions?: string | null;
}

const DEMO = scenario as unknown as {
  drugs: DemoDrug[];
  variants: Record<string, SessionResult>;
};

export function demoDrugs(): Drug[] {
  return DEMO.drugs.map(({ raw_name, strength, form, rxcui, display_name }) =>
    ({ raw_name, strength, form, rxcui, display_name }));
}

export function demoAmbiguities(): Ambiguity[] {
  return DEMO.drugs
    .filter((d) => d.rxcui === null && d.options)
    .map((d) => ({
      raw_name: d.raw_name, options: d.options ?? [], margin: d.margin,
      ingredient_rxcui: d.ingredient_rxcui,
    }));
}

/**
 * The demo's stand-in for POST /api/assess. Answers were computed ahead of
 * time by scripts/build_demo.py with the real resolver, so this is a lookup —
 * and a code set it has no answer for is an error, never a guess.
 */
export function assessDemo(codes: string[]): SessionResult {
  const key = codeSetFor(codes).codes.join(",");
  const hit = DEMO.variants[key];
  if (!hit) throw new Error(`the demo has no precomputed answer for ${key}`);
  return structuredClone(hit);
}

/**
 * Fold what only the browser knows — drugs outside the formulary, drugs the
 * user chose to leave out — into the server's codes-only answer. Mirrors
 * combine() in src/tessera/pipeline.py. Only ever makes a status worse.
 */
export function combine(
  result: SessionResult,
  local: { excluded: string[]; leftOut: string[] },
): SessionResult {
  const notes: string[] = [];
  if (local.excluded.length) {
    notes.push(`${local.excluded.length} medication(s) are outside Tessera's checked list, so `
      + `this result is incomplete: ${local.excluded.join(", ")}`);
  }
  if (local.leftOut.length) {
    notes.push(`You left these out rather than choose, so they were not checked: `
      + `${local.leftOut.join(", ")}.`);
  }
  const incomplete = local.excluded.length > 0 || local.leftOut.length > 0;
  return {
    ...result,
    excluded_drugs: [...local.excluded, ...local.leftOut],
    status: result.status === "ok" && incomplete ? "partial" : result.status,
    notes: [...notes, ...result.notes],
  };
}

/** The exact supporting text the demo builder verified inside a span, if any. */
export function demoHighlight(spanId: string): string | null {
  const spans = (scenario as unknown as { spans: Record<string, { highlight: string }> }).spans;
  return spans[spanId]?.highlight ?? null;
}
