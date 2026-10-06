// Host routing rules (ADR-001; SYSTEM_ARCHITECTURE 5): one app, three hosts, no cross-host routes.
import { describe, expect, it } from "vitest";

import { audienceForHost, hostsFromEnv, internalPath } from "@/lib/audience";

const hosts = hostsFromEnv({
  P2B_HOST_IHB: "plan2build.in",
  P2B_HOST_PRO: "Professionals.plan2build.in",
  P2B_HOST_OPS: "admin.plan2build.in",
});

describe("hostsFromEnv", () => {
  it("normalises host names", () => {
    expect(hosts.pro).toBe("professionals.plan2build.in");
  });

  it("fails fast when a host is missing", () => {
    expect(() => hostsFromEnv({ P2B_HOST_IHB: "a", P2B_HOST_PRO: "b" })).toThrow("P2B_HOST_OPS");
  });
});

describe("audienceForHost", () => {
  it.each([
    ["plan2build.in", "ihb"],
    ["PLAN2BUILD.IN:443", "ihb"],
    ["professionals.plan2build.in", "pro"],
    ["admin.plan2build.in:8080", "ops"],
  ])("maps %s to %s", (host, audience) => {
    expect(audienceForHost(host, hosts)).toBe(audience);
  });

  it.each([null, "", "evil.example", "plan2build.in.evil.example", "www.plan2build.in"])(
    "rejects %s",
    (host) => {
      expect(audienceForHost(host, hosts)).toBeNull();
    },
  );
});

describe("internalPath", () => {
  it("serves each host from its own segment", () => {
    expect(internalPath("ihb", "/")).toBe("/ihb");
    expect(internalPath("pro", "/leads/42")).toBe("/pro/leads/42");
  });

  it("cannot reach another audience's pages", () => {
    expect(internalPath("ihb", "/ops")).toBe("/ihb/ops");
    expect(internalPath("ihb", "/pro/leads")).toBe("/ihb/pro/leads");
  });
});
