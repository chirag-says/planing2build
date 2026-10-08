// Files are scanned before use (ADR-011): an action that names a file not yet AVAILABLE gets a 422
// on the file field. That answer means "wait and retry"; any other field error means "fix it".

type Answer = { status: number; body: unknown };

/** Field names that carry file ids in upload-backed requests. */
export const FILE_FIELDS = ["file_ids", "file_id"] as const;

/**
 * True when the only problem is that named files are still being checked: a 422 whose field
 * errors are all file fields. A 422 that also names another field is final, so it is shown at once.
 */
export function filesStillChecking(result: Answer, fileFields: readonly string[] = FILE_FIELDS): boolean {
  if (result.status !== 422) return false;
  const fields = (result.body as { error?: { details?: { fields?: Record<string, unknown> } } } | null)?.error?.details?.fields;
  if (!fields) return false;
  const names = Object.keys(fields);
  return names.length > 0 && names.some((n) => fileFields.includes(n)) && names.every((n) => fileFields.includes(n));
}
