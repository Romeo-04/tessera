import { describe, expect, it } from "vitest";
import { citeExcerpt } from "./cite";

const TEXT = "7 DRUG INTERACTIONS Diuretics: excessive drop in blood pressure. "
  + "Potassium-sparing diuretics (spironolactone, amiloride) can increase the risk of hyperkalemia. "
  + "Therefore, monitor the patient's serum potassium frequently. Lithium: toxicity.";

describe("citeExcerpt", () => {
  it("marks the exact supporting text when it is known", () => {
    const e = citeExcerpt(TEXT, "can increase the risk of hyperkalemia", []);
    expect(e.mark).toBe("can increase the risk of hyperkalemia");
    expect(e.pre + e.mark + e.post).toContain("Potassium-sparing diuretics");
  });

  it("falls back to the sentence naming the other drug", () => {
    const e = citeExcerpt(TEXT, null, ["Spironolactone"]);
    expect(e.mark).toContain("spironolactone");
    expect(e.mark.startsWith("Potassium-sparing")).toBe(true);
  });

  it("never marks anything it cannot locate", () => {
    const e = citeExcerpt(TEXT, "words that are not there", ["digoxin"]);
    expect(e.mark).toBe("");
    expect(e.pre.length).toBeGreaterThan(0);
  });

  it("is always a verbatim slice of the source", () => {
    const e = citeExcerpt(TEXT, "monitor the patient's serum potassium", []);
    const joined = (e.pre + e.mark + e.post).replace(/^…|…$/g, "");
    expect(TEXT).toContain(joined);
  });
});
