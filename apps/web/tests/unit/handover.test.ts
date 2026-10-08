// After a failed acknowledgement the API's error decides the next step: type the code again, ask
// for a new code (a used, locked or expired code, or a changed statement), or refresh the page.
import { describe, expect, it } from "vitest";

import { acknowledgeNext } from "@/lib/handover";

const body = (code: string, details?: Record<string, unknown>) => ({ error: { code, message: "", details } });

describe("acknowledgeNext", () => {
  it("lets a wrong code with attempts left be typed again", () => {
    expect(acknowledgeNext(400, body("OTP_INVALID", { attempts_left: 2 }))).toBe("retry");
  });

  it("asks for a new code when the code is used up", () => {
    expect(acknowledgeNext(423, body("OTP_LOCKED"))).toBe("newCode");
    expect(acknowledgeNext(400, body("OTP_INVALID", { reason: "expired" }))).toBe("newCode");
    expect(acknowledgeNext(400, body("OTP_INVALID", { reason: "used_or_replaced" }))).toBe("newCode");
    expect(acknowledgeNext(400, body("OTP_INVALID"))).toBe("newCode");
  });

  it("asks for a new code, with the current statement, when the statement changed", () => {
    expect(acknowledgeNext(409, body("STATE_CONFLICT", { reason: "STATEMENT_CHANGED" }))).toBe("newCode");
  });

  it("refreshes when the handover is no longer ready", () => {
    expect(acknowledgeNext(409, body("STATE_CONFLICT", { reason: "NOT_READY", current_state: "ACKNOWLEDGED" }))).toBe("refresh");
  });

  it("keeps the code on a network failure, a rate limit or a field error", () => {
    expect(acknowledgeNext(0, null)).toBe("retry");
    expect(acknowledgeNext(429, body("RATE_LIMITED"))).toBe("retry");
    expect(acknowledgeNext(422, body("VALIDATION_FAILED", { fields: { code: ["too short"] } }))).toBe("retry");
  });
});
