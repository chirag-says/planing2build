// Slice 3.4 end to end: a family with the package marks a service as needed, finds a listed
// professional through the directory, sends a connection request with their contact; the
// professional sees the brief only, accepts, and then sees the family's contact and the site pin;
// the family sees the professional's contact and the other open request withdrawn; the family
// records their own architect beside it; operations see the needs, requests and engagements. In a
// second test a professional declines with a reason the family never sees. Axe on every screen, phone and desktop.
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import {
  IHB,
  OPS,
  PRO,
  acceptWithChecklist,
  animationsDone,
  expectAccessible as axe,
  signInByCode,
  sql,
  staffReady,
  submitRequirement,
  uniqueEmail,
  type Submitted,
  openSection,
} from "./support";

async function openFromQueue(page: Page, code: string) {
  const link = page.getByRole("link", { name: code, exact: true });
  const next = page.getByRole("link", { name: "Next page" });
  await expect(async () => {
    await page.goto(`${OPS}/queue`);
    while ((await link.count()) === 0 && (await next.count()) > 0) {
      const before = page.url();
      await next.click();
      await page.waitForURL((url) => url.href !== before);
    }
    await expect(link).toBeVisible({ timeout: 1_000 });
  }).toPass({ timeout: 30_000 });
  await link.click();
}

/** Accepted by a fresh OPS reviewer, with the package bought through the development checkout. */
async function projectWithPackage(page: Page, request: APIRequestContext): Promise<Submitted> {
  const project = await submitRequirement(page, request);
  await staffReady(page, request);
  await openFromQueue(page, project.code);
  await page.getByRole("button", { name: "Claim for review" }).click();
  await acceptWithChecklist(page);
  await page.goto(`${IHB}/projects/${project.id}/package`);
  await page.getByText("In full now").click();
  await page.getByLabel("Name on the invoice").fill("Asha Verma");
  await page.getByLabel("Billing address").fill("12 Civil Lines, Raipur");
  await page.getByLabel("State").selectOption({ label: "Chhattisgarh" });
  await page.getByLabel(/I accept the purchase and refund terms/).check();
  await page.getByRole("button", { name: "Continue to payment" }).click();
  await expect(page).toHaveURL(/\/package\/orders\/[0-9a-f-]+$/);
  await page.getByRole("button", { name: /^Pay ₹/ }).click();
  const checkout = page.getByRole("dialog", { name: "Test payment" });
  await animationsDone(checkout);
  await checkout.getByRole("button", { name: "Pay (test)" }).click();
  await expect(page.getByText("Status: Paid")).toBeVisible({ timeout: 45_000 });
  return project;
}

/** A professional signs up on their host; the listing itself is seeded (approval is 3.2's spec). */
async function listedProfessional(page: Page, request: APIRequestContext, name: string, category: string) {
  const email = uniqueEmail();
  await page.goto(`${PRO}/sign-in`);
  await signInByCode(page, request, email);
  await expect(page.getByLabel("Your professional identity")).toBeVisible({
    timeout: 30_000,
  });
  const profileId = sql(`
    UPDATE professional_profiles SET display_name = '${name}', firm_name = '${name} LLP',
      base_locality = 'Civil Lines', base_geom = ST_GeogFromText('SRID=4326;POINT(81.64 21.24)'),
      service_radius_km = 25
    WHERE user_id = (SELECT user_id FROM user_contacts WHERE normalized = '${email}')
    RETURNING id;`).split("\n")[0];
  sql(`INSERT INTO professional_categories (id, profile_id, category_code, listing_state, listed_at)
       VALUES (gen_random_uuid(), '${profileId}', '${category}', 'LISTED', now());`);
  return profileId;
}

test("a family connects with a listed contractor, records their own architect, and operations see both", async ({
  page,
  request,
}) => {
  test.setTimeout(300_000);
  const suffix = Date.now().toString(36);
  const contractor = `E2E Builders ${suffix}`;
  const other = `E2E Other ${suffix}`;
  const project = await projectWithPackage(page, request);

  // Professionals for the project: one card per service.
  await page.goto(`${IHB}/projects/${project.id}`);
  await openSection(page, "Professionals");
  await expect(page).toHaveURL(`${IHB}/projects/${project.id}/services`);
  await expect(page.getByRole("heading", { name: "Professionals for your project" })).toBeVisible();
  await axe(page);

  const contractorCard = page.locator("#CONTRACTOR");
  await contractorCard.getByText("Yes, I need this").click();
  await contractorCard.getByRole("button", { name: "Save" }).click();
  await expect(contractorCard.getByText("Saved.")).toBeVisible();
  await expect(contractorCard.getByText("0 of 3 open requests")).toBeVisible();

  // Two listed contractors near the plot.
  const otherId = await listedProfessional(page, request, other, "CONTRACTOR");
  const builderId = await listedProfessional(page, request, contractor, "CONTRACTOR");

  // The directory, for this service and this plot.
  await page.goto(`${IHB}/projects/${project.id}/services`);
  await contractorCard.getByRole("link", { name: "Find a professional: Contractor" }).click();
  await expect(page.getByText("Showing Contractor professionals who serve your project's area.")).toBeVisible();
  await axe(page);
  await page.goto(`${IHB}/professionals/${builderId}?project=${project.id}&category=CONTRACTOR`);
  await expect(page.getByRole("heading", { level: 1, name: contractor })).toBeVisible();
  await axe(page);
  await page.getByRole("link", { name: "Request a connection" }).click();

  // The request: what the professional sees, and when.
  await expect(page.getByRole("heading", { name: "Request a connection" })).toBeVisible();
  await expect(page.getByText(/They have 48 hours to respond/)).toBeVisible();
  await axe(page);
  await page.getByLabel("Your name").fill("Meera Iyer");
  await page.getByLabel("Your phone number").fill("+91 98765 43210");
  await page.getByRole("button", { name: "Send request" }).click();
  await expect(page.getByText("Request sent.")).toBeVisible();
  await expect(contractorCard.getByText("Waiting for a response")).toBeVisible();
  await expect(contractorCard.getByText("1 of 3 open requests")).toBeVisible();
  await axe(page);

  // A second open request in the same service (up to three may be open, N-05).
  await page.goto(`${IHB}/projects/${project.id}/services/connect?category=CONTRACTOR&profile=${otherId}`);
  await page.getByLabel("Your name").fill("Meera Iyer");
  await page.getByLabel("Your phone number").fill("+91 98765 43210");
  await page.getByRole("button", { name: "Send request" }).click();
  await expect(page.getByText("Request sent.")).toBeVisible();

  // The professionals host is signed in as the builder (the latest sign-in there).
  await page.goto(`${PRO}/connections`);
  await expect(page.getByRole("heading", { name: "Connection requests" })).toBeVisible();
  await axe(page);
  await page.getByRole("link", { name: "View request: Contractor" }).first().click();
  await expect(page.getByText("Shankar Nagar")).toBeVisible();
  await expect(page.getByText("Meera Iyer")).toHaveCount(0); // N-08: no identity before acceptance
  await expect(page.getByText("+91 98765 43210")).toHaveCount(0);
  await axe(page);
  await page.getByLabel("Phone for the family").fill("+91 90000 11111");
  await page.getByRole("button", { name: "Accept request" }).click();
  await expect(page.getByText("Status: Accepted")).toBeVisible();
  await expect(page.getByText("Meera Iyer")).toBeVisible();
  await expect(page.getByRole("link", { name: "+91 98765 43210" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open the site pin in OpenStreetMap" })).toBeVisible();
  await axe(page);

  // The family sees who they are working with, and the other request withdrawn.
  await page.goto(`${IHB}/projects/${project.id}/services`);
  await expect(contractorCard.getByText(`Working with: ${contractor}`)).toBeVisible();
  await expect(contractorCard.getByRole("link", { name: "+91 90000 11111" })).toBeVisible();
  await expect(
    contractorCard.getByText("Withdrawn because another professional was engaged for this service."),
  ).toBeVisible();
  await axe(page);

  // Their own architect, beside the Plan2Build contractor.
  const architectCard = page.locator("#ARCHITECT");
  await architectCard.getByRole("button", { name: "Record my own professional: Architect" }).click();
  const dialog = page.getByRole("dialog", { name: "Record your own professional" });
  await animationsDone(dialog);
  await axe(page);
  await dialog.getByLabel("Name").fill("Kavya Rao");
  await dialog.getByLabel("Phone or email").fill("kavya@example.in");
  await dialog.getByRole("button", { name: "Record professional" }).click();
  await expect(architectCard.getByText("Working with: Kavya Rao")).toBeVisible();
  await expect(architectCard.getByText("Your own professional")).toBeVisible();
  await axe(page);

  // Operations see needs, requests, engagements and history.
  await page.goto(`${OPS}/projects/${project.id}`);
  await expect(page.getByRole("heading", { name: "Professionals and connections" })).toBeVisible();
  await expect(page.getByText(`Contractor: ${contractor}`).first()).toBeVisible();
  await expect(page.getByText("Contractor: Kavya Rao").or(page.getByText("Architect: Kavya Rao"))).toBeVisible();
  await axe(page);
});

test("a professional declines with a reason; the family sees a neutral message", async ({ page, request }) => {
  test.setTimeout(300_000);
  const name = `E2E Decliner ${Date.now().toString(36)}`;
  const project = await projectWithPackage(page, request);
  const profileId = await listedProfessional(page, request, name, "CONTRACTOR");
  await page.goto(`${IHB}/projects/${project.id}/services/connect?category=CONTRACTOR&profile=${profileId}`);
  await page.getByLabel("Your name").fill("Meera Iyer");
  await page.getByLabel("Your phone number").fill("98765 43210");
  await page.getByRole("button", { name: "Send request" }).click();
  await expect(page.getByText("Request sent.")).toBeVisible();

  await page.goto(`${PRO}/connections`);
  await page.getByRole("link", { name: "View request: Contractor" }).first().click();
  await page.getByLabel("Reason").selectOption({ label: "Other" });
  await expect(page.getByRole("button", { name: "Decline" })).toBeDisabled(); // OTHER needs a note
  await page.getByLabel("Explain").fill("The plot is beyond the crew's current route.");
  await axe(page);
  await page.getByRole("button", { name: "Decline" }).click();
  await expect(page.getByText("You declined this request.")).toBeVisible();
  await axe(page);

  await page.goto(`${IHB}/projects/${project.id}/services`);
  const card = page.locator("#CONTRACTOR");
  await expect(card.getByText("This professional could not take your request. You can ask another professional.")).toBeVisible();
  await expect(page.getByText("beyond the crew")).toHaveCount(0);
  await axe(page);
});
