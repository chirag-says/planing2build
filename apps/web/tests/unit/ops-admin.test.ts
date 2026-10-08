// Which operations and ADMIN controls are offered for an API state (src/lib/ops-admin.ts).
import { describe, expect, it } from "vitest";

import {
  assembleMode,
  canRefreshCriteria,
  canRetireCard,
  canRevokeSignoff,
  documentHasWarranty,
  handoverControls,
  mfaSummary,
} from "@/lib/ops-admin";

describe("canRetireCard", () => {
  it("offers retiring a published card to ADMIN only", () => {
    expect(canRetireCard("PUBLISHED", true)).toBe(true);
    expect(canRetireCard("PUBLISHED", false)).toBe(false);
    expect(canRetireCard("DRAFT", true)).toBe(false);
    expect(canRetireCard("RETIRED", true)).toBe(false);
  });
});

describe("canRevokeSignoff", () => {
  it("allows a signed sign-off in review, issued or accepted", () => {
    for (const state of ["IN_REVIEW", "ISSUED", "ACCEPTED"] as const) {
      expect(canRevokeSignoff(state, "SIGNED")).toBe(true);
    }
  });

  it("refuses a void sign-off or a version in any other state", () => {
    expect(canRevokeSignoff("IN_REVIEW", "VOID")).toBe(false);
    for (const state of ["DRAFT", "CHANGES_REQUESTED", "SUPERSEDED", "WITHDRAWN"] as const) {
      expect(canRevokeSignoff(state, "SIGNED")).toBe(false);
    }
  });
});

describe("canRefreshCriteria", () => {
  it("is a draft-only action", () => {
    expect(canRefreshCriteria("DRAFT")).toBe(true);
    expect(canRefreshCriteria("IN_REVIEW")).toBe(false);
  });
});

describe("handoverControls", () => {
  it("only opens when there is no handover", () => {
    expect(handoverControls(null)).toEqual({
      open: true, editDocuments: false, confirmReady: false, reopenOrIssue: false, assemble: false,
    });
  });

  it("edits documents and confirms ready while open", () => {
    const c = handoverControls("OPEN");
    expect(c.editDocuments && c.confirmReady).toBe(true);
    expect(c.open || c.reopenOrIssue || c.assemble).toBe(false);
  });

  it("reopens or issues without the owner when ready", () => {
    const c = handoverControls("READY");
    expect(c.reopenOrIssue).toBe(true);
    expect(c.editDocuments || c.assemble).toBe(false);
  });

  it("assembles the Build Record once closed", () => {
    expect(handoverControls("ACKNOWLEDGED").assemble).toBe(true);
    expect(handoverControls("ISSUED_BY_OPERATIONS").assemble).toBe(true);
    expect(handoverControls("ACKNOWLEDGED").editDocuments).toBe(false);
  });
});

describe("documentHasWarranty", () => {
  it("finds a warranty that names the document", () => {
    const warranties = [{ document_id: null }, { document_id: "d1" }];
    expect(documentHasWarranty("d1", warranties)).toBe(true);
    expect(documentHasWarranty("d2", warranties)).toBe(false);
  });
});

describe("assembleMode", () => {
  it("starts version 1 when there is none", () => {
    expect(assembleMode([])).toBe("first");
  });

  it("re-assembles an existing draft", () => {
    expect(assembleMode([{ state: "ISSUED" }, { state: "DRAFT" }])).toBe("reassemble");
  });

  it("needs a correction reason after an issued version", () => {
    expect(assembleMode([{ state: "SUPERSEDED" }, { state: "ISSUED" }])).toBe("correction");
  });
});

describe("mfaSummary", () => {
  it("reads the second factor's state", () => {
    expect(mfaSummary({ enrolled: false, verified: false, recovery_codes_left: 0 })).toBe("notEnrolled");
    expect(mfaSummary({ enrolled: true, verified: true, recovery_codes_left: 0 })).toBe("noRecoveryCodes");
    expect(mfaSummary({ enrolled: true, verified: true, recovery_codes_left: 8 })).toBe("verified");
    expect(mfaSummary({ enrolled: true, verified: false, recovery_codes_left: 8 })).toBe("notVerified");
  });
});
