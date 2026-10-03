import { describe, expect, it } from "vitest";
import { fitLongEdge } from "./photoSize";

describe("fitLongEdge", () => {
  it("shrinks a landscape photo by its width", () => {
    expect(fitLongEdge(4032, 3024)).toEqual({ width: 1600 });
  });
  it("shrinks a portrait photo by its height", () => {
    expect(fitLongEdge(3024, 4032)).toEqual({ height: 1600 });
  });
  it("leaves a small photo alone rather than enlarging it", () => {
    expect(fitLongEdge(1200, 900)).toBeNull();
  });
  it("leaves a photo of unknown size alone", () => {
    expect(fitLongEdge(0, 0)).toBeNull();
  });
});
