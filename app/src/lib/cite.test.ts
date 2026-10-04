import { describe, expect, it } from "vitest";
import { citeExcerpt, classNote } from "./cite";

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

describe("class citations", () => {
  it("marks the sentence with the class phrase the label used", () => {
    const e = citeExcerpt(TEXT, null, ["Furosemide"], "Diuretics");
    expect(e.mark).toContain("Diuretics: excessive drop in blood pressure.");
    expect(e.mark).not.toContain("Potassium");
  });

  it("matches a short class phrase too, case-insensitively", () => {
    const e = citeExcerpt("Avoid use with NSAIDs. Lithium: toxicity.", null, [], "nsaids");
    expect(e.mark).toBe("Avoid use with NSAIDs.");
  });

  it("explains why the quote does not name the drug", () => {
    expect(classNote({ via_class: "ACE inhibitors", subject_name: "Metformin", object_name: "Lisinopril" }))
      .toBe("The metformin label warns about “ACE inhibitors” rather than naming lisinopril. Lisinopril is one of them.");
    expect(classNote({ via_class: null, subject_name: "A", object_name: "B" })).toBeNull();
  });

  it("does not invent a name it does not have", () => {
    expect(classNote({ via_class: "NSAIDs", subject_name: null, object_name: null }))
      .toBe("The label warns about “NSAIDs” rather than naming this medication. It is one of them.");
  });
});
