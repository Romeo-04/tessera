import { describe, expect, it } from "vitest";
import { watchView } from "./watch";

const alert = (rxcui: string) => ({ rxcui, title: "t", url: "https://www.fda.gov/x", published: null, summary: "s" });

describe("watchView", () => {
  it("never shows an all-clear when the server could not be reached", () => {
    expect(watchView(null, ["RXCUI:1"]).kind).toBe("unreachable");
  });

  it("says the watcher has not run rather than that nothing was found", () => {
    expect(watchView({ generated_at: null, alerts: [], unchecked: [] }, ["RXCUI:1"]).kind).toBe("never_run");
  });

  it("keeps only this list's alerts", () => {
    const v = watchView({ generated_at: "2026-10-03", alerts: [alert("RXCUI:1"), alert("RXCUI:2")], unchecked: [] }, ["RXCUI:2"]);
    expect(v.kind === "ran" && v.alerts.map((a) => a.rxcui)).toEqual(["RXCUI:2"]);
  });

  it("names this list's drugs that the last run could not check, and is not clear", () => {
    const v = watchView({ generated_at: "2026-10-03", alerts: [], unchecked: ["RXCUI:2", "RXCUI:9"] }, ["RXCUI:1", "RXCUI:2"]);
    expect(v.kind === "ran" && v.unchecked).toEqual(["RXCUI:2"]);
    expect(v.kind === "ran" && v.clear).toBe(false);
  });

  it("is clear only when it ran, checked every drug on the list, and found nothing", () => {
    const v = watchView({ generated_at: "2026-10-03", alerts: [], unchecked: ["RXCUI:9"] }, ["RXCUI:1"]);
    expect(v.kind === "ran" && v.clear).toBe(true);
  });

  it("treats an older file without an unchecked field as checked-unknown, not clear", () => {
    const v = watchView({ generated_at: "2026-10-03", alerts: [] } as never, ["RXCUI:1"]);
    expect(v.kind === "ran" && v.clear).toBe(false);
  });
});
