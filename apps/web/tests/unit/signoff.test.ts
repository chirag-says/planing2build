// Which structural sign-offs may be revoked, and what revoking does (BP-20).
import { describe, expect, it } from "vitest";

import { revokeEffect } from "@/lib/signoff";

const listed = { state: "SIGNED", signer_kind: "LISTED" };

describe("revokeEffect", () => {
  it("voids a signed sign-off while the version is in review", () => {
    expect(revokeEffect(listed, "IN_REVIEW")).toBe("void");
  });
  it("records a revocation after issue or acceptance", () => {
    expect(revokeEffect(listed, "ISSUED")).toBe("afterIssue");
    expect(revokeEffect(listed, "ACCEPTED")).toBe("afterIssue");
  });
  it("offers nothing the API would refuse", () => {
    for (const s of ["DRAFT", "CHANGES_REQUESTED", "SUPERSEDED", "WITHDRAWN"] as const) expect(revokeEffect(listed, s)).toBeNull();
    expect(revokeEffect({ ...listed, state: "VOID" }, "IN_REVIEW")).toBeNull();
    expect(revokeEffect({ ...listed, signer_kind: "OUTSIDE" }, "IN_REVIEW")).toBeNull();
  });
});
