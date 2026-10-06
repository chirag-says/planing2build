// Foundation smoke: one app, three hosts, real API behind each (ADR-001, ADR-016, SECURITY 6).
import { expect, test } from "@playwright/test";

import { expectAccessible, signInLink } from "./support";

const ORIGIN = {
  ihb: process.env.E2E_IHB_ORIGIN ?? "http://ihb.localhost:8080",
  pro: process.env.E2E_PRO_ORIGIN ?? "http://pro.localhost:8080",
  ops: process.env.E2E_OPS_ORIGIN ?? "http://admin.localhost:8080",
};

// Every host shows the account in the header; on the professionals and operations hosts `/`
// leads to sign-in (professionals register there too, Slice 3.2).
const SHELLS = [
  { origin: ORIGIN.ihb, title: "The cheapest quote is almost never the cheapest house." },
  { origin: ORIGIN.pro, title: "Sign in or register" },
  { origin: ORIGIN.ops, title: "Staff sign-in" },
];

for (const { origin, title } of SHELLS) {
  test(`${origin} serves its own audience and reads the session from the API`, async ({ page }) => {
    const response = await page.goto(`${origin}/`);
    expect(response?.status()).toBe(200);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(title);
    await expect(await signInLink(page)).toBeVisible();
  });

  test(`${origin} passes automated accessibility checks`, async ({ page }) => {
    await page.goto(`${origin}/`);
    await expectAccessible(page);
  });
}

test("a page of one audience does not exist on another host", async ({ page }) => {
  expect((await page.goto(`${ORIGIN.ihb}/pro`))?.status()).toBe(404);
  expect((await page.goto(`${ORIGIN.pro}/ops`))?.status()).toBe(404);
});

// Navigation, not the `request` fixture: the browser resolves *.localhost, Node on Windows does not.
test("the API answers same-origin with the error envelope and no-store", async ({ page }) => {
  const response = await page.goto(`${ORIGIN.ihb}/api/v1/me`);
  if (!response) throw new Error("no response");
  expect(response.status()).toBe(401);
  expect(response.headers()["cache-control"]).toBe("no-store");
  const body = await response.json();
  expect(body.error.code).toBe("UNAUTHENTICATED");
  expect(body.error.request_id).toBe(response.headers()["x-request-id"]);
});

test("pages carry the app's security headers", async ({ page }) => {
  const response = await page.goto(`${ORIGIN.ihb}/`);
  if (!response) throw new Error("no response");
  const headers = response.headers();
  expect(headers["x-frame-options"]).toBe("DENY");
  expect(headers["x-content-type-options"]).toBe("nosniff");
  expect(headers["x-powered-by"]).toBeUndefined();
});
