// Slice 3.5 end to end (functional screens): the family provides drawings and submits them;
// operations record the appointed checker's approval, draft a Build Plan version, submit it,
// record an outside engineer's signed document; the last editor cannot issue, another operator
// issues; the family accepts the exact version with an emailed one-time code; the contractor
// manifest carries quantities and no internal rate. Reference data (a DEMO item rate card and an
// appointed checker) is seeded. Axe on every screen, phone and desktop.
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import {
  IHB,
  MAILPIT,
  OPS,
  PNG,
  acceptWithChecklist,
  animationsDone,
  expectAccessible as axe,
  sql,
  staffReady,
  submitRequirement,
  type Submitted,
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

/** A DEMO item card (development values) and an appointed checker without an account. */
function seedReferenceData(suffix: string) {
  sql(`
    WITH admin AS (SELECT id FROM users ORDER BY created_at LIMIT 1),
    card AS (
      INSERT INTO item_rate_cards (id, geography, version, status, is_demo, effective_from,
        source_reference, prepared_by)
      SELECT gen_random_uuid(), 'E2E ${suffix}', 1, 'DRAFT', true, current_date,
        'TEST values for end-to-end tests', id FROM admin RETURNING id)
    INSERT INTO item_rate_card_lines (id, card_id, item_code, description, unit, rate)
    SELECT gen_random_uuid(), card.id, 'TEST-RCC', 'TEST concrete', 'cum', 100.00 FROM card;
    UPDATE item_rate_cards SET status = 'PUBLISHED', published_at = now(),
      published_by = prepared_by WHERE geography = 'E2E ${suffix}';
    INSERT INTO drawing_checker_appointments (id, name, qualification, appointed_by)
    SELECT gen_random_uuid(), 'E2E Checker ${suffix}', 'Registered architect (TEST)', id
    FROM users ORDER BY created_at LIMIT 1;`);
}

async function upload(scope: ReturnType<Page["locator"]>, name: string) {
  await scope.getByLabel("File").setInputFiles({ name, mimeType: "image/png", buffer: PNG });
}

async function confirmationCode(request: APIRequestContext, email: string): Promise<string> {
  for (let attempt = 0; attempt < 40; attempt++) {
    const search = await request.get(`${MAILPIT}/api/v1/search`, {
      params: { query: `to:"${email}" subject:"confirmation code"` },
    });
    const { messages } = (await search.json()) as { messages: { ID: string }[] };
    if (messages.length > 0) {
      const message = await (await request.get(`${MAILPIT}/api/v1/message/${messages[0].ID}`)).json();
      const match = /\b(\d{6})\b/.exec(message.Text as string);
      if (match) return match[1];
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`no confirmation code arrived for ${email}`);
}

async function editJson(page: Page, label: string, change: (value: unknown) => unknown) {
  const box = page.getByLabel(label);
  const value = JSON.parse(await box.inputValue()) as unknown;
  await box.fill(JSON.stringify(change(value)));
}

test("drawings are checked, a Build Plan version is signed, issued by another operator and accepted with a code", async ({
  page,
  request,
}) => {
  test.setTimeout(420_000);
  const suffix = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 5)}`;
  const project = await projectWithPackage(page, request);
  seedReferenceData(suffix);
  const ownerEmail = sql(`SELECT c.normalized FROM user_contacts c JOIN projects p ON p.owner_user_id = c.user_id
    WHERE p.id = '${project.id}' AND c.is_primary`);

  // The family provides their own drawings.
  await page.goto(`${IHB}/projects/${project.id}/build-plan`);
  await expect(page.getByRole("heading", { name: "Build Plan", exact: true })).toBeVisible();
  await axe(page);
  await page.getByText("Ask for drawings").click();
  await page.getByLabel("Who provides the drawings").selectOption({ label: "I already have drawings" });
  await page.getByLabel("What the drawings should cover").fill("Our approved house drawings");
  await page.getByRole("button", { name: "Create request" }).click();
  await page.getByRole("button", { name: "Start a drawing set" }).click();
  const set = page.getByRole("region", { name: "Drawing set 1" });
  await expect(set.getByText("Draft")).toBeVisible();
  for (const [type, title] of [
    ["Site plan", "Site"], ["Floor plan", "Ground floor"], ["Elevation", "Front"],
    ["Section", "Section A"], ["Structural drawing", "RCC"],
  ] as const) {
    await upload(set, `${title}.png`);
    await set.getByLabel("Drawing type").selectOption({ label: type });
    await set.getByLabel("Title").fill(title);
    await set.getByRole("button", { name: "Add drawing" }).click();
    await expect(set.getByText(new RegExp(`${type}: ${title}`))).toBeVisible();
  }
  await axe(page);
  // Files are scanned by the worker before the set can be submitted.
  await expect(async () => {
    await page.reload();
    await page.getByRole("region", { name: "Drawing set 1" }).getByRole("button", { name: "Submit the set" }).click();
    await expect(page.getByText("Being checked")).toBeVisible({ timeout: 2_000 });
  }).toPass({ timeout: 60_000 });

  // Operations record the appointed checker's approval with the checker's signed note.
  await page.goto(`${OPS}/projects/${project.id}/build-plan`);
  await axe(page);
  const opsSet = page.getByRole("region", { name: "Drawing set 1" });
  await opsSet.getByLabel("Checker", { exact: true }).selectOption({ label: `E2E Checker ${suffix}` });
  await opsSet.getByLabel("Check note").fill("Drawings checked against the site.");
  await opsSet.getByLabel(/Signed note/).setInputFiles({ name: "note.png", mimeType: "image/png", buffer: PNG });
  await expect(async () => {
    await opsSet.getByRole("button", { name: "Approve" }).click();
    await expect(page.getByText("Approved", { exact: true })).toBeVisible({ timeout: 3_000 });
  }).toPass({ timeout: 60_000 });

  // A draft version, completed through the functional editors.
  await page.getByRole("button", { name: "New draft version" }).click();
  await page.getByRole("link", { name: "Open version 1" }).click();
  await expect(page.getByText(/Still needed:/)).toBeVisible();
  await axe(page);
  await page.getByRole("button", { name: "Use this approved set" }).click();
  await expect(page.getByText(/DRAWING_SET/)).toHaveCount(0);
  await editJson(page, "Values (JSON)", (values) =>
    (values as { code: string }[]).map((v) => ({
      code: v.code, applicability: "APPLICABLE", value_text: `TEST value ${v.code}`, basis: "ADVISOR",
    })),
  );
  await page.getByRole("button", { name: "Save" }).nth(0).click();
  await expect(page.getByText(/VALUE_A01/)).toHaveCount(0);
  await editJson(page, "BOQ (JSON with rate_card_id and lines)", () => ({
    rate_card_id: sql(`SELECT id FROM item_rate_cards WHERE geography = 'E2E ${suffix}'`),
    lines: [{ item_code: "TEST-RCC", quantity: "10", quantity_basis: "ADVISOR_ESTIMATE", basis_note: "E2E", stage_number: 3 }],
  }));
  await page.getByRole("button", { name: "Save" }).nth(1).click();
  await expect(page.getByText(/Still needed:.*\bBOQ\b/)).toHaveCount(0);
  await editJson(page, "Schedule (JSON entries)", (entries) =>
    (entries as { entry_key: string }[]).map((e) => ({ entry_key: e.entry_key, duration_days: 7, predecessors: [] })),
  );
  await page.getByRole("button", { name: "Save" }).nth(2).click();
  await expect(page.getByText(/DURATION_/)).toHaveCount(0);
  await page.getByLabel("Inclusions (one per line)").fill("Civil and structural work");
  await page.getByLabel("Exclusions (one per line)").fill("None.");
  await page.getByLabel("Assumptions (one per line)").fill("Soil as per the soil report");
  await page.getByRole("button", { name: "Save" }).nth(3).click();
  await expect(page.getByText(/Still needed:/)).toHaveCount(0);
  await axe(page);
  await page.getByRole("button", { name: "Submit for review" }).click();
  await expect(page.getByText("Status: In review")).toBeVisible();

  // An outside engineer's signed document for every structural line.
  await page.getByLabel("Engineer's name").fill("S. Rao");
  await page.getByLabel("Registration number").fill("TEST-REG-1");
  await page.getByLabel("Registration issued by").fill("TEST council");
  await page.getByLabel("Registration certificate").setInputFiles({ name: "cert.png", mimeType: "image/png", buffer: PNG });
  await page.getByLabel("Signed document").setInputFiles({ name: "signed.png", mimeType: "image/png", buffer: PNG });
  await page.getByLabel("Your check of the credential").fill("Checked against the register.");
  await expect(async () => {
    await page.getByRole("button", { name: "Record sign-off" }).click();
    await expect(page.getByText(/A19: S\. Rao/)).toBeVisible({ timeout: 3_000 });
  }).toPass({ timeout: 60_000 });
  await axe(page);

  // The last editor cannot issue; another operator does.
  await page.getByRole("button", { name: "Issue" }).click();
  await expect(page.getByText(/LAST_EDITOR/)).toBeVisible();
  const versionUrl = page.url();
  await page.context().clearCookies({ domain: new URL(OPS).hostname });
  await staffReady(page, request);
  await page.goto(versionUrl);
  await page.getByRole("button", { name: "Issue" }).click();
  await expect(page.getByText("Status: Issued")).toBeVisible();
  await axe(page);

  // The family accepts the exact version with an emailed one-time code.
  await page.goto(`${IHB}/projects/${project.id}/build-plan`);
  await page.getByRole("link", { name: "Open version 1" }).click();
  await expect(page.getByText("Status: Issued")).toBeVisible();
  await expect(page.getByText("Durations and dependencies only. Dates are not calculated yet.")).toBeVisible();
  await axe(page);
  await page.getByRole("button", { name: "Email me a code" }).click();
  await expect(page.getByText(/We sent a code to/)).toBeVisible();
  await page.getByLabel("6-digit code").fill(await confirmationCode(request, ownerEmail));
  await page.getByRole("button", { name: "Confirm acceptance" }).click();
  await expect(page.getByText("You accepted this version.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Download the accepted copy" })).toBeVisible();
  await axe(page);

  // The contractor manifest: quantities, never Plan2Build's rates.
  await page.goto(`${OPS}/projects/${project.id}/build-plan`);
  await page.getByRole("button", { name: "Show manifest" }).click();
  const manifest = page.getByTestId("rfq-manifest");
  await expect(manifest).toContainText('"quantities"');
  await expect(manifest).not.toContainText('"rate"');
  await expect(manifest).not.toContainText("100.00");
  await axe(page);
});
