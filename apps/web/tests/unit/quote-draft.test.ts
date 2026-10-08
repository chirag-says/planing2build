// The contractor's quote form as data: what a draft keeps, how it is restored, what is submitted.
import { describe, expect, it } from "vitest";

import { emptyQuoteForm, fromDraft, toDraft, toQuote, validRate, type QuoteFormState } from "@/lib/quote-draft";

const TODAY = "2026-10-08";
const LINES = [1, 2, 3];
const form = (patch: Partial<QuoteFormState>): QuoteFormState => ({ ...emptyQuoteForm(TODAY), ...patch });

describe("validRate", () => {
  it("accepts positive amounts with up to two decimals", () => {
    expect(validRate("1250")).toBe(true);
    expect(validRate(" 99.5 ")).toBe(true);
    expect(validRate("0.01")).toBe(true);
  });
  it("rejects what the API would refuse", () => {
    for (const v of ["", "0", "0.00", "-5", "1.234", "abc", "12345678901", "1e3"]) expect(validRate(v)).toBe(false);
  });
});

describe("toDraft", () => {
  it("keeps only lines with a valid rate or an exclusion", () => {
    const body = toDraft(form({ rates: { 1: "100", 2: "12.", 3: "" }, excluded: {} }), LINES);
    expect(body.lines).toEqual([{ line_no: 1, excluded: false, rate: "100" }]);
  });
  it("keeps an exclusion without a reason, and its reason once typed", () => {
    const body = toDraft(form({ excluded: { 1: "", 2: " not in scope " }, rates: { 1: "50" } }), LINES);
    expect(body.lines).toEqual([
      { line_no: 1, excluded: true },
      { line_no: 2, excluded: true, exclusion_reason: "not in scope" },
    ]);
  });
  it("ignores lines that are not in the request", () => {
    expect(toDraft(form({ rates: { 9: "100" } }), LINES).lines).toEqual([]);
  });
  it("drops half-typed dates, durations out of range and empty text", () => {
    const body = toDraft(form({ validFrom: "2026-10", validTo: "", duration: "0", terms: "  ", warranty: "1 year" }), LINES);
    expect(body).toEqual({ lines: [], tax_treatment: "EXCLUSIVE", warranty: "1 year" });
  });
  it("keeps valid dates, duration and attachments", () => {
    const body = toDraft(form({ validTo: "2026-12-31", duration: "120", attachmentIds: ["a", "b"], tax: "INCLUSIVE" }), LINES);
    expect(body).toMatchObject({ valid_from: TODAY, valid_to: "2026-12-31", duration_days: 120, tax_treatment: "INCLUSIVE", attachment_file_ids: ["a", "b"] });
  });
  it("never sends text longer than the API allows", () => {
    expect(toDraft(form({ materials: "x".repeat(2001) }), LINES).materials).toBeUndefined();
    expect(toDraft(form({ duration: "3651" }), LINES).duration_days).toBeUndefined();
  });
});

describe("fromDraft", () => {
  it("starts empty without a draft", () => {
    expect(fromDraft(null, LINES, TODAY)).toEqual(emptyQuoteForm(TODAY));
    expect(fromDraft("nonsense", LINES, TODAY)).toEqual(emptyQuoteForm(TODAY));
  });
  it("restores the API's stored draft", () => {
    const stored = {
      lines: [
        { line_no: 1, rate: "100.50", excluded: false, exclusion_reason: null, alternate_spec: null },
        { line_no: 2, rate: null, excluded: true, exclusion_reason: "by owner", alternate_spec: null },
        { line_no: 7, rate: "1", excluded: false },
      ],
      additional_items: [], valid_from: "2026-10-10", valid_to: "2026-11-30", tax_treatment: "INCLUSIVE",
      tax_note: null, duration_days: 90, stage_durations: [], payment_terms: "30/70", warranty: null,
      materials: "Contractor", exclusions: [], assumptions: [], attachment_file_ids: ["f1"], comment: null,
    };
    expect(fromDraft(stored, LINES, TODAY)).toEqual({
      rates: { 1: "100.50" }, excluded: { 2: "by owner" }, validFrom: "2026-10-10", validTo: "2026-11-30",
      tax: "INCLUSIVE", duration: "90", terms: "30/70", warranty: "", materials: "Contractor", attachmentIds: ["f1"],
    });
  });
  it("round-trips through toDraft", () => {
    const state = form({ rates: { 1: "10", 3: "7.25" }, excluded: { 2: "n/a" }, validTo: "2027-01-01", duration: "30", terms: "Monthly", attachmentIds: ["x"] });
    expect(fromDraft(toDraft(state, LINES), LINES, TODAY)).toEqual(state);
  });
  it("ignores an unknown tax treatment", () => {
    expect(fromDraft({ tax_treatment: "ZERO" }, LINES, TODAY).tax).toBe("EXCLUSIVE");
  });
});

describe("toQuote", () => {
  it("sends every line, priced or excluded, with the attachments", () => {
    const body = toQuote(form({ rates: { 1: " 10 " }, excluded: { 2: "" }, validTo: "2027-01-01", duration: "30", attachmentIds: ["a"] }), LINES);
    expect(body.lines).toEqual([
      { line_no: 1, excluded: false, rate: "10" },
      { line_no: 2, excluded: true, exclusion_reason: "" },
      { line_no: 3, excluded: false, rate: null },
    ]);
    expect(body).toMatchObject({ valid_from: TODAY, valid_to: "2027-01-01", duration_days: 30, tax_treatment: "EXCLUSIVE", attachment_file_ids: ["a"] });
    expect(body).not.toHaveProperty("payment_terms");
  });
});
