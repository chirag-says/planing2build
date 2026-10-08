// When a 422 means "the files are still being scanned" (retry) and when it means "fix the form".
import { describe, expect, it } from "vitest";

import { filesStillChecking } from "@/lib/file-check";

const answer = (status: number, fields?: Record<string, string[]>) => ({
  status,
  body: fields ? { error: { code: "VALIDATION_FAILED", message: "", details: { fields } } } : null,
});

describe("filesStillChecking", () => {
  it("is true for a 422 only on the file field", () => {
    expect(filesStillChecking(answer(422, { file_ids: ["Upload the photos and wait for the check."] }))).toBe(true);
    expect(filesStillChecking(answer(422, { file_id: ["Upload the document first."] }))).toBe(true);
  });
  it("uses the fields given", () => {
    const quote = answer(422, { attachment_file_ids: ["Upload the files and wait for the check."] });
    expect(filesStillChecking(quote)).toBe(false);
    expect(filesStillChecking(quote, ["attachment_file_ids"])).toBe(true);
  });
  it("is false when another field is wrong too", () => {
    expect(filesStillChecking(answer(422, { attachment_file_ids: ["wait"], "lines.2": ["Price it"] }), ["attachment_file_ids"])).toBe(false);
  });
  it("is false for other answers", () => {
    expect(filesStillChecking(answer(201))).toBe(false);
    expect(filesStillChecking(answer(409, { file_ids: ["x"] }))).toBe(false);
    expect(filesStillChecking(answer(422))).toBe(false);
    expect(filesStillChecking(answer(422, {}))).toBe(false);
    expect(filesStillChecking({ status: 0, body: null })).toBe(false);
  });
});
