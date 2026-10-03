import { describe, expect, it } from "vitest";
import { screenQuestion } from "./guardrail";
import type { Drug } from "./types";

const drug = (name: string, rxcui: string): Drug =>
  ({ raw_name: name.toUpperCase(), strength: null, form: null, rxcui, display_name: name });

const LIST: Drug[] = [
  drug("Lisinopril", "RXCUI:29046"), drug("Furosemide", "RXCUI:4603"),
  drug("Warfarin", "RXCUI:11289"), drug("Spironolactone", "RXCUI:9997"),
  drug("Digoxin", "RXCUI:3407"), drug("Metformin", "RXCUI:6809"),
  drug("Atorvastatin", "RXCUI:83367"),
];

describe("screenQuestion refuses dose and treatment decisions", () => {
  it.each([
    "Should I lower his warfarin dose until we see the doctor?",
    "is it ok to skip his warfarin tonight",
    "Can I give him half a tablet of digoxin?",
    "stop the spironolactone?",
    "How many mg of furosemide should he take",
    "can she double up on metformin if she missed one",
    "Should he come off atorvastatin",
    "could I swap the lisinopril for something else",
    "what is the maximum dosage",
    // Indirect phrasings a reviewer found answered rather than refused.
    "Should I adjust his warfarin because of the atorvastatin?",
    "Can I split his warfarin tablet",
    "Should he take less warfarin",
    "Should I hold the warfarin",
    "Should he keep taking warfarin with the statin",
    "Can he have more of the water pill",
    "should she take fewer metformin",
    "can I give warfarin every other day",
    "should we hold off on the digoxin",
    "can I crush the metformin",
    "should he still take lisinopril",
    "give him another furosemide tonight?",
  ])("refuses %j", (q) => {
    expect(screenQuestion(q, LIST).kind).toBe("refuse");
  });

  it.each([
    "he has chest pain after taking it",
    "she took too many pills",
    "he cannot breathe properly",
  ])("sends %j to emergency care, not to an answer", (q) => {
    expect(screenQuestion(q, LIST).kind).toBe("urgent");
  });
});

describe("screenQuestion answers what the labels can", () => {
  it("resolves lay names to the drugs on this list", () => {
    const r = screenQuestion("Can he take the water pill with the blood pressure one at breakfast?", LIST);
    expect(r.kind).toBe("answer");
    if (r.kind === "answer") {
      expect(r.codes).toContain("RXCUI:29046");
      expect(r.codes).toContain("RXCUI:4603");
    }
  });

  it("matches drugs by name, case-insensitively", () => {
    const r = screenQuestion("is WARFARIN ok with atorvastatin", LIST);
    expect(r.kind).toBe("answer");
    if (r.kind === "answer") expect([...r.codes].sort()).toEqual(["RXCUI:11289", "RXCUI:83367"]);
  });

  it("asks for two medications when it can find fewer", () => {
    expect(screenQuestion("is this one safe?", LIST).kind).toBe("clarify");
  });

  it("does not match a lay name for a drug that is not on the list", () => {
    const short = LIST.filter((d) => d.display_name !== "Furosemide" && d.display_name !== "Spironolactone");
    expect(screenQuestion("water pill with the blood pressure one?", short).kind).toBe("clarify");
  });
});
