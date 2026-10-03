// Mirrors src/tessera/schemas.py. The server never sends names on /api/assess;
// subject_name/object_name are filled in here, from what the browser already knew.

export type Severity = "contraindicated" | "warning" | "monitor";

export type Status =
  | "ok"
  | "partial"
  | "analysis_incomplete"
  | "insufficient_drugs"
  | "no_drugs_detected";

export interface Candidate {
  rxcui: string;
  display_name: string;
  score: number;
}

export interface RankedRisk {
  subject: string;
  object: string;
  subject_name: string | null;
  object_name: string | null;
  severity: Severity;
  mechanism: string;
  span_id: string;
  source_url: string;
  action: string;
  quote: string | null;
}

export interface ConfirmationRequest {
  raw_name: string;
  options: Candidate[];
}

export interface SessionResult {
  risks: RankedRisk[];
  excluded_drugs: string[];
  unchecked_drugs: string[];
  needs_confirmation: ConfirmationRequest[];
  status: Status;
  notes: string[];
}

/** One bottle, as read. Lives in the browser only. */
export interface Drug {
  raw_name: string;
  strength: string | null;
  form: string | null;
  rxcui: string | null;
  display_name: string | null;
}

/** A drug the normaliser refused to guess, and what it could not choose between. */
export interface Ambiguity {
  raw_name: string;
  options: Candidate[];
  margin?: number;
  /** Demo only: the options it holds a precomputed answer for. */
  precomputed?: string[];
}

/** One request that crossed (or, in the demo, would cross) a network boundary. */
export interface WireEntry {
  boundary: "photos" | "codes";
  method: "POST" | "GET";
  url: string;
  body: string;
  sent: boolean;
}
