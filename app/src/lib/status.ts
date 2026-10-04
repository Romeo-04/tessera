import type { RankedRisk, Status } from "./types";

/** "Warfarin + Atorvastatin", or the bare code where the device has no name - never an invented one. */
export function pairLabel(r: RankedRisk): string {
  return `${r.subject_name ?? r.subject} + ${r.object_name ?? r.object}`;
}

/**
 * What each status means to a caregiver. An empty risk list is ambiguous, and
 * the ambiguity is what hurts people: "nothing found", "could not read your
 * photos" and "found something we could not explain" all produce zero risks.
 * Only "ok" may ever imply that the check was complete.
 */
export function statusCopy(status: Status, riskCount: number): { title: string; body: string } {
  const counted = riskCount === 1 ? "1 thing to raise" : `${riskCount} things to raise`;
  switch (status) {
    case "ok":
      return riskCount > 0
        ? { title: counted, body: "Most severe first. Tap one to read the label text it came from." }
        : {
            title: "Nothing documented between these",
            body: "Their FDA labels, as held in Tessera's corpus, document no interaction between "
              + "these medications. That is not the same as safe — a pharmacist can check "
              + "what labels do not cover.",
          };
    case "partial":
      return {
        title: riskCount > 0 ? `${counted} — list incomplete` : "Checked part of the list",
        body: "Some medications could not be checked. The notes below say which, so nothing "
          + "here is a clean bill of health for them.",
      };
    case "analysis_incomplete":
      return {
        title: "Found more than we could explain",
        body: "The labels document interactions we could not put into words reliably, so they "
          + "are not shown. Please take this list to a pharmacist.",
      };
    case "insufficient_drugs":
      return {
        title: "Need at least two medications",
        body: "Interactions are between medications, and fewer than two were identified. "
          + "Add a photo of the other bottles, or confirm any we asked about.",
      };
    case "no_drugs_detected":
      return {
        title: "Could not read the labels",
        body: "We could not read any medication labels in these photographs. Try again with "
          + "the labels facing the camera, in good light.",
      };
  }
}
