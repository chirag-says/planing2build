// What the owner can do after a failed handover acknowledgement (Slice 3.7C, EX-15), read from the
// API's error only. A wrong code with attempts left can be typed again; a locked, expired, used or
// replaced code, or a statement that changed, needs a new code (which also returns the current
// statement); a handover that is no longer ready needs the page refreshed.

export type AcknowledgeNext = "retry" | "newCode" | "refresh";

interface ApiError {
  code?: string;
  details?: Record<string, unknown> | null;
}

export function acknowledgeNext(status: number, body: unknown): AcknowledgeNext {
  const error = (body as { error?: ApiError } | null)?.error;
  const code = error?.code;
  const reason = error?.details?.reason;
  if (code === "OTP_LOCKED") return "newCode";
  if (code === "OTP_INVALID") return typeof error?.details?.attempts_left === "number" ? "retry" : "newCode";
  if (code === "STATE_CONFLICT") return reason === "STATEMENT_CHANGED" ? "newCode" : "refresh";
  if (code === "RATE_LIMITED" || status === 0 || status === 422 || status >= 500) return "retry";
  return "newCode";
}
