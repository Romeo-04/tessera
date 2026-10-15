import { describe, expect, it } from "vitest";
import type { ReadResult } from "./api";
import { classLine, drugName, tidyRead } from "./names";

describe("drugName", () => {
  it("capitalises an RxNorm ingredient the way the demo shows it", () => {
    expect(drugName("lisinopril")).toBe("Lisinopril");
    expect(drugName("insulin glargine")).toBe("Insulin glargine");
  });

  it("leaves a name that already has capitals alone", () => {
    expect(drugName("Lisinopril")).toBe("Lisinopril");
    expect(drugName("WARF SOD")).toBe("WARF SOD");
  });

  it("passes null through rather than inventing a name", () => {
    expect(drugName(null)).toBeNull();
    expect(drugName("")).toBe("");
  });
});

describe("tidyRead", () => {
  const read: ReadResult = {
    drugs: [{ raw_name: "LISINOPRIL", strength: "10MG", form: null, rxcui: "RXCUI:29046",
              display_name: "lisinopril", confidence: 1, in_formulary: true }],
    excluded: [],
    confirmations: [{ raw_name: "WARF SOD", options: [
      { rxcui: "RXCUI:11289", display_name: "warfarin", score: 1 }] }],
    unreadable: false,
  };

  it("names every drug and every option the same way, without touching codes", () => {
    const out = tidyRead(read);
    expect(out.drugs[0].display_name).toBe("Lisinopril");
    expect(out.drugs[0].rxcui).toBe("RXCUI:29046");
    expect(out.confirmations[0].options[0].display_name).toBe("Warfarin");
  });

  it("does not mutate the server's answer", () => {
    tidyRead(read);
    expect(read.drugs[0].display_name).toBe("lisinopril");
  });
});

describe("classLine", () => {
  it("says on the card that the label named the class, not the drug", () => {
    expect(classLine({ via_class: "antidiabetic medicines" }))
      .toBe("The label warns about “antidiabetic medicines”, which includes this drug.");
  });

  it("says nothing for a label that names the drug", () => {
    expect(classLine({ via_class: null })).toBeNull();
    expect(classLine({})).toBeNull();
  });
});
