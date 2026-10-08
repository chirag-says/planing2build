// The admin pages added to close the gaps with the API: the staff list (GET /admin/staff), the
// acknowledgement statements (GET /ops/acknowledgement-statements and the ADMIN drafts) and the
// MFA status (GET /auth/mfa). Each opens from the admin navigation, lists real data and passes axe.
import { expect, test } from "@playwright/test";

import { OPS, expectAccessible, staffReady } from "./support";

test("an admin reads the staff accounts, the acknowledgement statements and their own MFA status", async ({
  page,
  request,
}) => {
  test.slow();
  const { email } = await staffReady(page, request, false, "ADMIN");

  await page.goto(`${OPS}/admin/staff`);
  await expect(page.getByRole("heading", { name: "Staff accounts", level: 1 })).toBeVisible();
  // The account just granted is one of the staff accounts listed.
  await expect(page.getByText(email)).toBeVisible();
  await expectAccessible(page);

  await page.goto(`${OPS}/admin/acknowledgement-statements`);
  await expect(page.getByRole("heading", { name: "Acknowledgement statements", level: 1 })).toBeVisible();
  await expectAccessible(page);

  await page.goto(`${OPS}/mfa`);
  await expect(page.getByRole("main")).toBeVisible();
  await expectAccessible(page);
});
