// A drawing being checked is polled until its state settles, and never forever.
import { describe, expect, it } from "vitest";

import { isScanPending, SCAN_POLL_MAX, shouldPollScan } from "@/lib/file-scan";

describe("file scan polling", () => {
  it("polls only while the file is uploaded or scanning", () => {
    expect(isScanPending("UPLOADED")).toBe(true);
    expect(isScanPending("SCANNING")).toBe(true);
    for (const state of ["AVAILABLE", "QUARANTINED", "FAILED", "DELETED", "PENDING_UPLOAD"]) {
      expect(isScanPending(state)).toBe(false);
      expect(shouldPollScan(state, 0)).toBe(false);
    }
  });

  it("stops after the last attempt", () => {
    expect(shouldPollScan("SCANNING", SCAN_POLL_MAX - 1)).toBe(true);
    expect(shouldPollScan("SCANNING", SCAN_POLL_MAX)).toBe(false);
  });
});
