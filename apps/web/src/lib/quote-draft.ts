// The contractor's quote form as data (Slice 3.6): the working copy saved as a draft (QuoteDraftIn,
// every field optional, never part of the record), restored from the invitation's `draft`, and the
// complete quote submitted (QuoteIn). The draft keeps only values the API accepts, so an autosave
// never fails on a half-typed field; the submission sends everything and lets the API list the
// lines to fix.
import type { components } from "@p2b/contracts";

export type QuoteDraftBody = components["schemas"]["QuoteDraftIn"];
export type QuoteBody = components["schemas"]["QuoteIn"];
export type TaxTreatment = components["schemas"]["TaxTreatment"];

export type QuoteFormState = {
  /** Unit rate as typed, by RFQ line number. */
  rates: Record<number, string>;
  /** Exclusion reason as typed, by line number; absent or null when the line is priced. */
  excluded: Record<number, string | null>;
  validFrom: string;
  validTo: string;
  tax: TaxTreatment;
  duration: string;
  terms: string;
  warranty: string;
  materials: string;
  attachmentIds: string[];
};

export const TEXT_MAX = 2000;
const SHORT_MAX = 500;
const ATTACHMENTS_MAX = 20;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const RATE = /^\d{1,10}(\.\d{1,2})?$/;
const DAYS = /^\d{1,4}$/;
const TAX: readonly TaxTreatment[] = ["INCLUSIVE", "EXCLUSIVE"];

export function emptyQuoteForm(today: string): QuoteFormState {
  return {
    rates: {}, excluded: {}, validFrom: today, validTo: "", tax: "EXCLUSIVE", duration: "",
    terms: "", warranty: "", materials: "", attachmentIds: [],
  };
}

/** A rate the API accepts: positive, at most two decimals, below 10^10. */
export function validRate(value: string): boolean {
  const v = value.trim();
  return RATE.test(v) && Number(v) > 0;
}

function days(value: string): number | null {
  const v = value.trim();
  if (!DAYS.test(v)) return null;
  const n = Number(v);
  return n >= 1 && n <= 3650 ? n : null;
}

function text(value: string, max: number): string | null {
  const v = value.trim();
  return v && v.length <= max ? v : null;
}

/** The working copy to save: only values the draft schema accepts; the rest wait for the next save. */
export function toDraft(state: QuoteFormState, lineNumbers: number[]): QuoteDraftBody {
  const lines: NonNullable<QuoteDraftBody["lines"]> = [];
  for (const n of lineNumbers) {
    const reason = state.excluded[n];
    if (reason != null) {
      const why = text(reason, SHORT_MAX);
      lines.push(why ? { line_no: n, excluded: true, exclusion_reason: why } : { line_no: n, excluded: true });
    } else if (state.rates[n] !== undefined && validRate(state.rates[n])) {
      lines.push({ line_no: n, excluded: false, rate: state.rates[n].trim() });
    }
  }
  const body: QuoteDraftBody = { lines, tax_treatment: state.tax };
  if (DATE.test(state.validFrom)) body.valid_from = state.validFrom;
  if (DATE.test(state.validTo)) body.valid_to = state.validTo;
  const d = days(state.duration);
  if (d !== null) body.duration_days = d;
  const terms = text(state.terms, TEXT_MAX);
  if (terms) body.payment_terms = terms;
  const warranty = text(state.warranty, TEXT_MAX);
  if (warranty) body.warranty = warranty;
  const materials = text(state.materials, TEXT_MAX);
  if (materials) body.materials = materials;
  if (state.attachmentIds.length > 0) body.attachment_file_ids = state.attachmentIds.slice(0, ATTACHMENTS_MAX);
  return body;
}

const asRecord = (v: unknown): Record<string, unknown> | null =>
  v !== null && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : null;
const asString = (v: unknown): string => (typeof v === "string" ? v : typeof v === "number" ? String(v) : "");

/** The form restored from the invitation's `draft` (an untyped object), for the RFQ's lines only. */
export function fromDraft(draft: unknown, lineNumbers: number[], today: string): QuoteFormState {
  const state = emptyQuoteForm(today);
  const d = asRecord(draft);
  if (!d) return state;
  const known = new Set(lineNumbers);
  for (const raw of Array.isArray(d.lines) ? d.lines : []) {
    const line = asRecord(raw);
    const n = line ? Number(line.line_no) : NaN;
    if (!line || !known.has(n)) continue;
    if (line.excluded === true) state.excluded[n] = asString(line.exclusion_reason);
    else if (line.rate !== null && line.rate !== undefined) state.rates[n] = asString(line.rate);
  }
  if (typeof d.valid_from === "string" && DATE.test(d.valid_from)) state.validFrom = d.valid_from;
  if (typeof d.valid_to === "string" && DATE.test(d.valid_to)) state.validTo = d.valid_to;
  if (TAX.includes(d.tax_treatment as TaxTreatment)) state.tax = d.tax_treatment as TaxTreatment;
  if (typeof d.duration_days === "number") state.duration = String(d.duration_days);
  state.terms = asString(d.payment_terms);
  state.warranty = asString(d.warranty);
  state.materials = asString(d.materials);
  if (Array.isArray(d.attachment_file_ids)) {
    state.attachmentIds = d.attachment_file_ids.filter((id): id is string => typeof id === "string");
  }
  return state;
}

/** The complete quote: every line priced or excluded; the API names what is missing (QD-18). */
export function toQuote(state: QuoteFormState, lineNumbers: number[]): QuoteBody {
  return {
    lines: lineNumbers.map((n) =>
      state.excluded[n] != null
        ? { line_no: n, excluded: true, exclusion_reason: state.excluded[n] || "" }
        : { line_no: n, excluded: false, rate: state.rates[n]?.trim() || null },
    ),
    valid_from: state.validFrom,
    valid_to: state.validTo,
    tax_treatment: state.tax,
    duration_days: Number(state.duration) || 0,
    ...(state.terms.trim() ? { payment_terms: state.terms } : {}),
    ...(state.warranty.trim() ? { warranty: state.warranty } : {}),
    ...(state.materials.trim() ? { materials: state.materials } : {}),
    attachment_file_ids: state.attachmentIds,
  };
}
