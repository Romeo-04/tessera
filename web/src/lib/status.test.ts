import { describe, expect, it } from "vitest";
import { statusCopy } from "./status";
import type { Status } from "./types";

const ALL: Status[] = ["ok", "partial", "analysis_incomplete", "insufficient_drugs", "no_drugs_detected"];

describe("statusCopy", () => {
  it("gives every status its own title", () => {
    const titles = ALL.map((s) => statusCopy(s, 0).title);
    expect(new Set(titles).size).toBe(ALL.length);
  });

  it("never tells someone with an incomplete result that nothing was found", () => {
    for (const s of ALL.filter((x) => x !== "ok")) {
      const { title, body } = statusCopy(s, 0);
      expect(`${title} ${body}`.toLowerCase()).not.toMatch(/no (documented )?interactions/);
    }
  });

  it("says plainly that an empty ok result is not a guarantee", () => {
    expect(statusCopy("ok", 0).body.toLowerCase()).toContain("not the same as safe");
  });

  it("counts the risks when there are some", () => {
    expect(statusCopy("ok", 5).title).toBe("5 things to raise");
    expect(statusCopy("ok", 1).title).toBe("1 thing to raise");
  });
});
