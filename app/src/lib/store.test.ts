import { describe, expect, it } from "vitest";
import { forgetList, loadList, saveList, type KV } from "./store";
import type { Drug } from "./types";

function memory(): KV & { raw: Map<string, string> } {
  const raw = new Map<string, string>();
  return {
    raw,
    getItem: async (k) => raw.get(k) ?? null,
    setItem: async (k, v) => { raw.set(k, v); },
    removeItem: async (k) => { raw.delete(k); },
  };
}

const d = (name: string, rxcui: string | null): Drug =>
  ({ raw_name: name.toUpperCase(), strength: null, form: null, rxcui, display_name: name });

describe("saved list", () => {
  it("round-trips the coded drugs", async () => {
    const kv = memory();
    await saveList([d("warfarin", "RXCUI:11289"), d("aspirin", "RXCUI:1191")], kv, new Date("2026-10-03T10:00:00Z"));
    const got = await loadList(kv);
    expect(got?.drugs.map((x) => x.rxcui)).toEqual(["RXCUI:11289", "RXCUI:1191"]);
    expect(got?.savedAt).toBe("2026-10-03T10:00:00.000Z");
  });

  it("does not save drugs that carry no code", async () => {
    const kv = memory();
    await saveList([d("warfarin", "RXCUI:11289"), d("smudged", null)], kv);
    expect((await loadList(kv))?.drugs).toHaveLength(1);
  });

  it("forgetting really forgets", async () => {
    const kv = memory();
    await saveList([d("warfarin", "RXCUI:11289")], kv);
    await forgetList(kv);
    expect(await loadList(kv)).toBeNull();
    expect(kv.raw.size).toBe(0);
  });

  it("treats corrupt data as no list, not a crash", async () => {
    const kv = memory();
    kv.raw.set("tessera.list", "{not json");
    expect(await loadList(kv)).toBeNull();
  });

  it("rejects an entry whose code is not a code", async () => {
    const kv = memory();
    kv.raw.set("tessera.list", JSON.stringify({ version: 1, savedAt: "x", drugs: [{ raw_name: "A", rxcui: "warfarin", display_name: "a" }] }));
    expect(await loadList(kv)).toBeNull();
  });

  it("ignores a list written by a different schema version", async () => {
    const kv = memory();
    kv.raw.set("tessera.list", JSON.stringify({ version: 99, savedAt: "x", drugs: [] }));
    expect(await loadList(kv)).toBeNull();
  });

  it("an empty list is no list", async () => {
    const kv = memory();
    await saveList([d("smudged", null)], kv);
    expect(await loadList(kv)).toBeNull();
  });
});
