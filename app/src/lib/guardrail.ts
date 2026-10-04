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

// Checked first. Any SYMPTOM the person has now goes to emergency care, never
// to a citation - however well-sourced the citation. A list of exact emergency
// phrases always misses one ("drowsy and confused", "swollen lips"); a broad
// symptom vocabulary fails the safe way: a symptom question that did not need
// the emergency message gets it anyway, and still learns nothing it should not.
const URGENT = new RegExp(
  [
    // breathing, heart, consciousness
    "chest (pain|tight\\w*)", "can'?t breathe", "cannot breathe", "trouble breathing", "short(ness)? of breath",
    "breathless", "wheez\\w*", "heart (is )?(racing|pounding|fluttering|skipping)", "palpitations?",
    "unconscious", "unresponsive", "not responding", "won'?t wake", "can'?t wake", "hard to wake",
    "passed out", "faint(ed|ing)?", "collaps\\w*", "seizure", "fit", "stroke", "slurred",
    "drowsy", "confus\\w*", "disoriented", "dizzy", "dizziness", "light-?headed", "weak(ness)?", "numb\\w*",
    // allergy
    "rash", "hives", "itch\\w*", "swell\\w*", "swollen", "puffy",
    // bleeding, gut
    "bleed\\w*", "blood in", "bruis\\w*", "black stools?", "vomit\\w*", "throwing up", "diarrh\\w*",
    // falls, overdose
    "fell", "fall(en)?", "hit (his|her|their) head",
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
    // Indirect forms: adjusting, splitting, holding, continuing, frequency.
    "adjust(ing)?", "titrat(e|ing)", "split(ting)?", "crush(ing)?", "chew(ing)?",
    "cut (it|them|the|his|her|a|in)", "less", "fewer",
    "(take|have|give|giving|taking)( \\w+){0,3} (more|another)",
    "hold(ing)?( off)?", "keep (taking|giving|on)", "still (take|taking|give|giving|on)",
    "continu(e|ing)", "every other", "twice", "times a day", "per day",
    // Timing changes are dosing decisions as well.
    "apart", "space (out|them)", "spaced", "spacing", "\\d+ hours?",
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
      message: "Tessera does not assess symptoms. If this is happening now and seems serious — "
        + "trouble breathing, swelling, confusion, not waking, heavy bleeding, a fall — call your "
        + "local emergency number. Otherwise, call the pharmacist or doctor today and describe it.",
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
