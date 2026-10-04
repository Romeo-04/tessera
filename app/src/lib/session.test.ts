import { describe, expect, it } from "vitest";
import { assessDemo, codeSetFor, combine, demoAmbiguities, demoDrugs, rejoinNames } from "./session";
import type { RankedRisk, SessionResult } from "./types";

const risk = (subject: string, object: string): RankedRisk => ({
  subject, object, subject_name: null, object_name: null, severity: "warning",
  mechanism: "m", span_id: "s", source_url: "https://dailymed.nlm.nih.gov/x",
  action: "Ask a pharmacist.", quote: null,
});

const result = (risks: RankedRisk[]): SessionResult => ({
  risks, excluded_drugs: [], unchecked_drugs: [], needs_confirmation: [], status: "ok", notes: [],
});

describe("rejoinNames", () => {
  it("names the codes the browser already knew", () => {
    const out = rejoinNames(result([risk("RXCUI:1", "RXCUI:2")]), [
      { raw_name: "A", strength: null, form: null, rxcui: "RXCUI:1", display_name: "Alpha" },
      { raw_name: "B", strength: null, form: null, rxcui: "RXCUI:2", display_name: "Beta" },
    ]);
    expect(out.risks[0].subject_name).toBe("Alpha");
    expect(out.risks[0].object_name).toBe("Beta");
  });

  it("leaves an unknown code unnamed rather than inventing a name", () => {
    const out = rejoinNames(result([risk("RXCUI:1", "RXCUI:9")]), [
      { raw_name: "A", strength: null, form: null, rxcui: "RXCUI:1", display_name: "Alpha" },
    ]);
    expect(out.risks[0].object_name).toBeNull();
  });

  it("does not mutate the server's result", () => {
    const original = result([risk("RXCUI:1", "RXCUI:2")]);
    rejoinNames(original, []);
    expect(original.risks[0].subject_name).toBeNull();
  });
});

describe("codeSetFor", () => {
  it("sends sorted, unique codes and nothing else", () => {
    const body = codeSetFor(["RXCUI:9", "RXCUI:10", "RXCUI:9"]);
    expect(Object.keys(body)).toEqual(["codes"]);
    expect(body.codes).toEqual(["RXCUI:10", "RXCUI:9"]);
  });

  it("refuses to put anything that is not a code on the wire", () => {
    expect(() => codeSetFor(["RXCUI:1", "warfarin"])).toThrow();
  });
});

describe("the seeded demo", () => {
  const known = demoDrugs().filter((d) => d.rxcui).map((d) => d.rxcui as string);
  const warfarin = demoAmbiguities()[0].options[0].rxcui;

  it("has seven bottles and one it refuses to guess", () => {
    expect(demoDrugs()).toHaveLength(7);
    expect(demoAmbiguities()).toHaveLength(1);
  });

  it("with the ambiguous drug confirmed, shows five of six and says so", () => {
    const r = assessDemo([...known, warfarin]);
    expect(r.risks).toHaveLength(5);
    expect(r.status).toBe("ok");
    expect(r.notes.join(" ")).toContain("6 documented interactions");
  });

  it("with the ambiguous drug left out, is partial and names what was left out", () => {
    const r = assessDemo(known);
    expect(r.status).toBe("partial");
    expect(r.excluded_drugs).toEqual(["WARF SOD"]);
  });

  it("refuses a code set it has no precomputed answer for, instead of guessing", () => {
    expect(() => assessDemo(["RXCUI:1", "RXCUI:2"])).toThrow();
  });
});

describe("combine", () => {
  it("downgrades ok to partial when something was left out or excluded", () => {
    const out = combine(result([]), { excluded: ["PHENPROCOUMON"], leftOut: [] });
    expect(out.status).toBe("partial");
    expect(out.excluded_drugs).toEqual(["PHENPROCOUMON"]);
    expect(out.notes[0]).toContain("PHENPROCOUMON");
  });

  it("never upgrades a worse status", () => {
    const bad = { ...result([]), status: "analysis_incomplete" as const };
    expect(combine(bad, { excluded: ["X"], leftOut: ["Y"] }).status).toBe("analysis_incomplete");
  });

  it("leaves a complete result alone", () => {
    expect(combine(result([]), { excluded: [], leftOut: [] }).status).toBe("ok");
  });
});
