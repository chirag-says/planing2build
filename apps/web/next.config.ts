import type { NextConfig } from "next";

// Headers the app owns (SECURITY_ARCHITECTURE 6). The nonce-based CSP lands with the first slice
// that ships interactive pages, report-only for a fortnight before it is enforced.
const SECURITY_HEADERS = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  // Camera and microphone open only on the auditor PWA routes when they exist.
  { key: "Permissions-Policy", value: "camera=(), microphone=()" },
];

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  // Variants are produced by the worker and served from R2; no image optimiser on the VPS.
  images: { unoptimized: true },
  transpilePackages: ["@p2b/contracts"],
  async headers() {
    return [{ source: "/:path*", headers: SECURITY_HEADERS }];
  },
};

export default nextConfig;
