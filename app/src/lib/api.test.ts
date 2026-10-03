import { afterEach, describe, expect, it, vi } from "vitest";
import { assessLive } from "./api";

afterEach(() => vi.unstubAllGlobals());

const ok = {
  risks: [], excluded_drugs: [], unchecked_drugs: [], needs_confirmation: [], status: "ok", notes: [],
};

describe("assessLive", () => {
  it("sends a body whose only key is codes", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify(ok), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await assessLive(["RXCUI:2", "RXCUI:1"]);
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({ codes: ["RXCUI:1", "RXCUI:2"] });
  });

  it("turns a spend-ceiling refusal into a demo fallback with the server's reason", async () => {
    const detail = "Today's live-checking budget is used up.";
    vi.stubGlobal("fetch", vi.fn(async () =>
      new Response(JSON.stringify({ detail, fallback: "demo" }), { status: 429 })));
    const r = await assessLive(["RXCUI:1", "RXCUI:2"]);
    expect(r).toEqual({ ok: false, reason: detail, fallback: true });
  });

  it("treats an unreachable server as a demo fallback, not a crash", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("Failed to fetch"); }));
    const r = await assessLive(["RXCUI:1", "RXCUI:2"]);
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.fallback).toBe(true);
  });

  it("does not offer the demo as a substitute for an upstream failure", async () => {
    vi.stubGlobal("fetch", vi.fn(async () =>
      new Response(JSON.stringify({ detail: "The model service failed." }), { status: 502 })));
    const r = await assessLive(["RXCUI:1", "RXCUI:2"]);
    expect(r).toEqual({ ok: false, reason: "The model service failed.", fallback: false });
  });
});

describe("a static host with no API behind it", () => {
  it("is not mistaken for a live server when it answers 200 with HTML", async () => {
    vi.stubGlobal("fetch", vi.fn(async () =>
      new Response("<!DOCTYPE html><html></html>", { status: 200, headers: { "Content-Type": "text/html" } })));
    const { liveAvailable, fetchAlerts } = await import("./api");
    expect(await liveAvailable()).toBe(false);
    expect(await fetchAlerts()).toBeNull();
  });
});

describe("photoParts", () => {
  it("on native, sends the file by uri so the bridge streams it", async () => {
    const { photoParts } = await import("./api");
    const parts = await photoParts([{ uri: "file:///p.jpg", name: "p.jpg", type: "image/jpeg" }], false);
    expect(parts[0]).toEqual({ uri: "file:///p.jpg", name: "p.jpg", type: "image/jpeg" });
  });

  it("on web, turns the picker's uri into a Blob", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(new Blob(["x"], { type: "image/jpeg" }))));
    const { photoParts } = await import("./api");
    const parts = await photoParts([{ uri: "blob:abc", name: "p.jpg", type: "image/jpeg" }], true);
    expect(parts[0]).toBeInstanceOf(Blob);
  });
});
