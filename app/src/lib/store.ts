import type { Drug } from "./types";

/**
 * The saved medication list. It lives on this device only - AsyncStorage on
 * a phone, localStorage in a browser - with no account and no server copy.
 * Anything unreadable is treated as "no list": a corrupt or foreign record
 * must never be re-checked as if it were someone's medications.
 */
export interface KV {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
  removeItem(key: string): Promise<void>;
}

export interface SavedList {
  savedAt: string;
  drugs: Drug[];
  /** Labels that were left out or outside scope when it was saved. A re-check
   *  must stay "incomplete" for them rather than come back as a clean result. */
  incomplete: string[];
}

const KEY = "tessera.list";
const VERSION = 1;
const RXCUI = /^RXCUI:[0-9]+$/;

export async function saveList(drugs: Drug[], kv: KV, now = new Date(), incomplete: string[] = []): Promise<void> {
  const coded = drugs
    .filter((d) => d.rxcui && RXCUI.test(d.rxcui))
    .map(({ raw_name, strength, form, rxcui, display_name }) => ({ raw_name, strength, form, rxcui, display_name }));
  if (coded.length === 0) {
    await kv.removeItem(KEY);
    return;
  }
  await kv.setItem(KEY, JSON.stringify({ version: VERSION, savedAt: now.toISOString(), drugs: coded, incomplete }));
}

function valid(d: unknown): d is Drug {
  if (!d || typeof d !== "object") return false;
  const x = d as Record<string, unknown>;
  return typeof x.raw_name === "string"
    && typeof x.rxcui === "string" && RXCUI.test(x.rxcui)
    && (x.display_name === null || typeof x.display_name === "string");
}

export async function loadList(kv: KV): Promise<SavedList | null> {
  let parsed: unknown;
  try {
    const raw = await kv.getItem(KEY);
    if (!raw) return null;
    parsed = JSON.parse(raw);
  } catch {
    return null;
  }
  const p = parsed as { version?: unknown; savedAt?: unknown; drugs?: unknown; incomplete?: unknown };
  if (p?.version !== VERSION || typeof p.savedAt !== "string" || !Array.isArray(p.drugs)) return null;
  const incomplete = p.incomplete ?? [];
  if (!Array.isArray(incomplete) || !incomplete.every((x) => typeof x === "string")) return null;
  if (p.drugs.length === 0 || !p.drugs.every(valid)) return null;
  return {
    savedAt: p.savedAt,
    drugs: p.drugs.map((d) => ({ raw_name: d.raw_name, strength: d.strength ?? null, form: d.form ?? null,
      rxcui: d.rxcui, display_name: d.display_name })),
    incomplete: incomplete as string[],
  };
}

export async function forgetList(kv: KV): Promise<void> {
  await kv.removeItem(KEY);
}
