import { codeSetFor } from "./session";
import type { ConfirmationRequest, Drug, SessionResult } from "./types";
import type { AlertsFile } from "./watch";

/** Empty means same origin (the dev proxy, or the API serving the app). */
const BASE = (import.meta.env?.VITE_API_URL as string | undefined) ?? "";

export type Outcome<T> =
  | { ok: true; value: T }
  | { ok: false; reason: string; fallback: boolean };

export interface ReadResult {
  drugs: (Drug & { confidence: number; in_formulary: boolean })[];
  excluded: string[];
  confirmations: ConfirmationRequest[];
  unreadable: boolean;
}

async function call<T>(path: string, init: RequestInit): Promise<Outcome<T>> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, init);
  } catch {
    return { ok: false, reason: "The live service could not be reached.", fallback: true };
  }
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    /* an empty or non-JSON body is reported by status below */
  }
  if (res.ok) {
    // A static host rewrites unknown paths to index.html with a 200. That is
    // "no API here", not a successful empty answer.
    if (body === null || typeof body !== "object") {
      return { ok: false, reason: "No live service is deployed here.", fallback: true };
    }
    return { ok: true, value: body as T };
  }

  const b = (body ?? {}) as { detail?: unknown; fallback?: string };
  const reason = typeof b.detail === "string" ? b.detail : `The live service answered ${res.status}.`;
  // Only refusals the server marks as demo-safe offer the demo. An upstream
  // failure mid-check does not: showing canned results there would look like
  // an answer about this person's medications.
  return { ok: false, reason, fallback: b.fallback === "demo" };
}

export async function liveAvailable(): Promise<boolean> {
  const r = await call<{ live: boolean }>("/health", { method: "GET" });
  return r.ok && r.value.live === true;
}

export function readLive(photos: File[]): Promise<Outcome<ReadResult>> {
  const form = new FormData();
  for (const p of photos) form.append("photos", p);
  return call<ReadResult>("/api/read", { method: "POST", body: form });
}

export async function assessLive(codes: string[]): Promise<
  { ok: true; result: SessionResult } | { ok: false; reason: string; fallback: boolean }
> {
  const r = await call<SessionResult>("/api/assess", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(codeSetFor(codes)),
  });
  return r.ok ? { ok: true, result: r.value } : r;
}

export interface Alert {
  rxcui: string;
  title: string;
  url: string;
  published: string | null;
  summary: string;
}

/** The whole formulary's alerts. Filtered in the browser (lib/watch.ts), so the
 *  server never learns whose list it is. Null when no server answered. */
export async function fetchAlerts(): Promise<AlertsFile | null> {
  const r = await call<AlertsFile>("/api/alerts", { method: "GET" });
  return r.ok ? r.value : null;
}
