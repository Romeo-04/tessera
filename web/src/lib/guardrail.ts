import type { Drug } from "./types";

/**
 * The refusal boundary for typed questions. Deterministic on purpose: a prompt
 * asking a model not to give dosing advice is a request, not a guarantee, and
 * this is the one place where "usually" is not good enough.
 *
 * Nothing here generates text. A question is either refused, sent to urgent
 * care, or mapped to two or more drugs on this person's list — and the answer
 * is then assembled from the already-cited risks, never written fresh.
 */

export type Screened =
  | { kind: "urgent"; message: string }
  | { kind: "refuse"; message: string }
  | { kind: "clarify"; message: string }
  | { kind: "answer"; codes: string[] };

// Checked first: a question describing an emergency must never be answered
// with a citation, however well-sourced.
const URGENT = new RegExp(
  [
    "chest pain", "can'?t breathe", "cannot breathe", "trouble breathing", "short(ness)? of breath",
    "unconscious", "passed out", "fainted", "seizure", "stroke", "slurred",
    "vomiting blood", "black stool", "bleeding (heavily|a lot|won'?t stop)",
    "took too many", "taken too many", "overdose", "swallowed (too many|extra|the wrong)",
  ].map((p) => `\\b${p}\\b`).join("|"),
  "i",
);

const DOSE_OR_TREATMENT = new RegExp(
  [
    "dose", "doses", "dosage", "dosing", "maximum", "max",
    "\\d+(\\.\\d+)?\\s*(mg|mcg|ml|g|units?)", "mg", "mcg",
    "how (much|many)", "half", "halve", "double", "triple", "extra",
    "skip", "skipping", "miss", "missed", "stop", "stopping", "quit", "discontinue", "pause",
    "cut (back|down|out)", "come off", "go off", "wean",
    "lower", "reduce", "decrease", "increase", "raise",
    "swap", "switch", "substitute", "replace", "instead of", "alternative",
    "(start|begin) (taking|giving|him|her|them|on)",
  ].map((p) => `\\b${p}\\b`).join("|"),
  "i",
);

/** Lay names caregivers actually use, mapped to ingredients. Only matched
 *  against drugs that are on this person's list. */
const LAY_NAMES: [RegExp, string[]][] = [
  [/\b(water|fluid) pills?\b|\bdiuretics?\b/i,
    ["furosemide", "spironolactone", "hydrochlorothiazide", "chlorthalidone", "torsemide", "bumetanide"]],
  [/\bblood pressure (one|pill|tablet|med|medicine|medication)s?\b/i,
    ["lisinopril", "losartan", "amlodipine", "metoprolol", "valsartan", "enalapril", "ramipril",
      "carvedilol", "atenolol", "olmesartan"]],
  [/\bblood thinners?\b|\banticoagulants?\b/i,
    ["warfarin", "apixaban", "rivaroxaban", "dabigatran", "clopidogrel"]],
  [/\bheart (one|pill|tablet|med|medicine|medication)s?\b/i, ["digoxin"]],
  [/\bcholesterol (one|pill|tablet|med|medicine|medication)s?\b|\bstatins?\b/i,
    ["atorvastatin", "simvastatin", "rosuvastatin", "pravastatin", "lovastatin"]],
  [/\b(diabetes|sugar) (one|pill|tablet|med|medicine|medication)s?\b/i,
    ["metformin", "glipizide", "glimepiride", "glyburide", "sitagliptin"]],
];

function ingredientOf(d: Drug): string {
  return (d.display_name ?? d.raw_name).toLowerCase().split(/[\s,]+/)[0] ?? "";
}

export function screenQuestion(question: string, drugs: Drug[]): Screened {
  if (URGENT.test(question)) {
    return {
      kind: "urgent",
      message: "That sounds like it may need care now. Call your local emergency number or "
        + "poison control. Tessera is not the right tool for this.",
    };
  }
  if (DOSE_OR_TREATMENT.test(question)) {
    return {
      kind: "refuse",
      message: "Changing, skipping or stopping a medication is a clinical decision, and Tessera "
        + "is not a clinical tool. Call the pharmacist or prescriber — and if there are "
        + "symptoms now, seek urgent care.",
    };
  }

  const codes = new Set<string>();
  const q = question.toLowerCase();
  for (const d of drugs) {
    if (!d.rxcui) continue;
    const ing = ingredientOf(d);
    if (ing.length >= 4 && new RegExp(`\\b${ing}\\b`).test(q)) codes.add(d.rxcui);
  }
  for (const [pattern, ingredients] of LAY_NAMES) {
    if (!pattern.test(question)) continue;
    for (const d of drugs) if (d.rxcui && ingredients.includes(ingredientOf(d))) codes.add(d.rxcui);
  }

  if (codes.size < 2) {
    return {
      kind: "clarify",
      message: "Name two of the medications on this list — by name, or as \"the water pill\", "
        + "\"the blood thinner\" — and Tessera will show what their labels document.",
    };
  }
  return { kind: "answer", codes: [...codes] };
}
