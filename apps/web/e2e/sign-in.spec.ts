// Homeowner sign-in by email OTP, end to end: browser, Caddy, Next.js, API, outbox, worker and the
// Mailpit email sink (SECURITY 3.1, 3.2; B-03). Needs the local stack and `pnpm dev:web`.
import { expect, test } from "@playwright/test";

import {
  IHB,
  codeFor,
  expectAccessible,
  openSignOut,
  signInLink,
  uniqueEmail,
} from "./support";

test("a homeowner signs up with an emailed code and signs out", async ({ page, request }) => {
  // Generous: in development the first visit to each route compiles it.
  test.setTimeout(90_000);
  const email = uniqueEmail();
  await page.goto(`${IHB}/`);
  await (await signInLink(page)).click();

  await page.getByLabel("Email address").fill(email);
  await page.getByRole("button", { name: "Email me a code" }).click();
  await expect(page.getByText(/We sent a code to/)).toBeVisible();
  await expectAccessible(page);

  await page.getByLabel("6-digit code").fill(await codeFor(request, email));
  await page.getByRole("button", { name: "Sign in" }).click();

  // A new family is asked once whether to describe the home now; skipping is a fine answer and
  // leads to the dashboard, which asks again.
  await expect(page).toHaveURL(`${IHB}/welcome`);
  await expect(page.getByRole("link", { name: "Tell us about my home" })).toBeVisible();
  await expectAccessible(page);
  await page.getByRole("link", { name: "Skip for now" }).click();
  await expect(page).toHaveURL(`${IHB}/projects`);
  await expect(page.getByRole("heading", { name: "Tell us about your home" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Start my requirement" })).toBeVisible();
  await expectAccessible(page);
  const signOut = await openSignOut(page);
  const cookies = await page.context().cookies();
  const session = cookies.find((cookie) => cookie.name.includes("p2b_ihb_session"));
  expect(session?.httpOnly).toBe(true);
  expect(session?.sameSite).toBe("Lax");
  expect(await page.evaluate(() => document.cookie)).not.toContain("p2b_ihb_session");

  await signOut.click();
  await expect(await signInLink(page)).toBeVisible();
});

test("a wrong code is refused with a readable message", async ({ page, request }) => {
  const email = uniqueEmail();
  await page.goto(`${IHB}/sign-in`);
  await page.getByLabel("Email address").fill(email);
  await page.getByRole("button", { name: "Email me a code" }).click();
  const code = await codeFor(request, email);
  const wrong = String((Number(code) + 1) % 1_000_000).padStart(6, "0");

  await page.getByLabel("6-digit code").fill(wrong);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toHaveText(/That code is not valid/);
  await expect(page.getByLabel("6-digit code")).toBeVisible();
  await expectAccessible(page);
});

test("the sign-in page passes automated accessibility checks", async ({ page }) => {
  await page.goto(`${IHB}/sign-in`);
  await expectAccessible(page);
});
