// Slice 3.6 end to end (functional screens): a family with the package and an ACCEPTED Build Plan
// (prepared through the API: the 3.5 spec covers those screens) asks for contractor quotes from
// two listed contractors; operations set the deadline and issue; each contractor sees the brief,
// agrees to quote, and quotes every line (one prices, one excludes with a reason); operations mark
// both reviewed and publish the comparison; the family sees prices only then, and selects one
// quote with an emailed one-time code; the selected contractor sees the family's contact through
// the engagement, the other sees "not selected". Axe on every screen, phone and desktop.
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import {
  IHB,
  OPS,
  PRO,
  api,
  codeCount,
  confirmationCode,
  contractor,
  expectAccessible as axe,
  projectWithPackage,
  sql,
  staffReady,
  type Submitted,
} from "./support";

const STRUCTURAL = ["A01", "A02", "A04", "A05", "A09", "A12", "A13", "A19"];
const CLASSES = ["SITE_PLAN", "FLOOR_PLAN", "ELEVATION", "SECTION", "STRUCTURAL"];

/** A scanned, AVAILABLE project file (the upload pipeline is covered by other specs). */
function storedFile(projectId: string, purpose: string, name: string): string {
  return sql(`INSERT INTO file_objects (id, bucket, object_key, purpose, owner_user_id, project_id,
      original_name, declared_mime, detected_mime, size_bytes, sha256, state)
    SELECT gen_random_uuid(), 'e2e', 'e2e/' || gen_random_uuid(), '${purpose}', owner_user_id, id,
      '${name}', 'application/pdf', 'application/pdf', 1000, md5(random()::text) || md5(random()::text),
      'AVAILABLE' FROM projects WHERE id = '${projectId}' RETURNING id;`).split("\n")[0];
}

/** The ACCEPTED Build Plan, through the API: the family's own architect's drawings, the appointed
 * checker's approval, a complete version signed by an outside engineer's document, issued by a
 * second operator, and accepted with the owner's emailed code. */
async function acceptedBuildPlan(page: Page, request: APIRequestContext, project: Submitted, suffix: string, ownerEmail: string) {
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
  const family = `/api/v1/projects/${project.id}`;
  const services = await api(page, IHB, "POST", `${family}/engagements`, { category: "ARCHITECT", name: "Own Architect" });
  const engagementId = (services.categories as { code: string; engagement: { id: string } }[])
    .find((c) => c.code === "ARCHITECT")!.engagement.id;
  let view = await api(page, IHB, "POST", `${family}/design-requests`, {
    kind: "OUTSIDE_PROFESSIONAL", engagement_id: engagementId, scope_note: "House drawings",
  });
  const requestId = (view.design_requests as { id: string }[]).at(-1)!.id;
  view = await api(page, IHB, "POST", `${family}/design-requests/${requestId}/sets`);
  const setId = (view.design_requests as { sets: { id: string }[] }[]).at(-1)!.sets.at(-1)!.id;
  for (const drawingClass of CLASSES) {
    const fileId = storedFile(project.id, "DRAWING", `${drawingClass}.pdf`);
    await api(page, IHB, "POST", `${family}/drawing-sets/${setId}/files`, { file_id: fileId, drawing_class: drawingClass, title: drawingClass });
  }
  await api(page, IHB, "POST", `${family}/drawing-sets/${setId}/submit`);
  const checker = sql(`SELECT id FROM drawing_checker_appointments WHERE name = 'E2E Checker ${suffix}'`);
  await api(page, OPS, "POST", `/api/v1/ops/drawing-sets/${setId}/check`, {
    appointment_id: checker, approve: true, note: "Checked.",
    evidence_file_id: storedFile(project.id, "BUILD_PLAN_EVIDENCE", "note.pdf"),
  });
  const version = await api(page, OPS, "POST", `/api/v1/ops/projects/${project.id}/build-plan/versions`);
  const snapshot = version.snapshot as { version: { id: string }; values: { code: string; is_structural: boolean }[]; schedule: { entry_key: string }[] };
  const vid = snapshot.version.id;
  const ops = `/api/v1/ops/build-plan-versions/${vid}`;
  await api(page, OPS, "PUT", `${ops}/drawing-set`, { set_id: setId });
  await api(page, OPS, "PUT", `${ops}/values`, {
    values: snapshot.values.map((v) => ({ code: v.code, value_text: `TEST value ${v.code}`, basis: v.is_structural ? "STRUCTURAL_DESIGN" : "ADVISOR" })),
  });
  await api(page, OPS, "PUT", `${ops}/boq`, {
    rate_card_id: sql(`SELECT id FROM item_rate_cards WHERE geography = 'E2E ${suffix}'`),
    lines: [{ item_code: "TEST-RCC", quantity: "12.5", quantity_basis: "ADVISOR_ESTIMATE", basis_note: "E2E", stage_number: 3 }],
  });
  await api(page, OPS, "PUT", `${ops}/schedule`, { entries: snapshot.schedule.map((e) => ({ entry_key: e.entry_key, duration_days: 7 })) });
  await api(page, OPS, "PUT", `${ops}/scope`, { inclusions: ["Civil and structural work"], exclusions: ["None."], assumptions: ["Soil as per the soil report"] });
  await api(page, OPS, "POST", `${ops}/submit`);
  await api(page, OPS, "POST", `${ops}/signoffs`, {
    line_codes: STRUCTURAL, engineer_name: "S. Rao (outside)", registration_number: "TEST-REG-1",
    registration_issuer: "TEST council", credential_file_id: storedFile(project.id, "BUILD_PLAN_EVIDENCE", "cert.pdf"),
    evidence_file_id: storedFile(project.id, "BUILD_PLAN_EVIDENCE", "signed.pdf"), attestation: "Checked against the register.",
  });
  await page.context().clearCookies({ domain: new URL(OPS).hostname });
  await staffReady(page, request);
  await api(page, OPS, "POST", `${ops}/issue`);
  const before = await codeCount(request, ownerEmail);
  const challenge = await api(page, IHB, "POST", `${family}/build-plan/versions/${vid}/acceptance-code`);
  const code = await confirmationCode(request, ownerEmail, before);
  await api(page, IHB, "POST", `${family}/build-plan/versions/${vid}/accept`, { challenge_id: challenge.challenge_id, code });
}

async function quote(page: Page, exclude: boolean) {
  await page.goto(`${PRO}/quotes`);
  await expect(page.getByRole("heading", { name: "Requests to quote" })).toBeVisible();
  await axe(page);
  await page.getByRole("link", { name: "Open" }).first().click();
  await expect(page.getByRole("heading", { name: "Project brief" })).toBeVisible();
  await expect(page.getByTestId("pack")).toHaveCount(0); // the brief only, before accepting
  await axe(page);
  await page.getByRole("button", { name: "Agree to quote" }).click();
  await expect(page.getByTestId("pack")).toBeVisible();
  await expect(page.getByTestId("pack")).not.toContainText("100.00"); // never Plan2Build's rate
  if (exclude) {
    await page.getByLabel("Exclude this line").check();
    await page.getByLabel("Why it is excluded").fill("Concrete supplied by the homeowner");
  } else {
    await page.getByLabel("Unit rate (INR)").fill("180.00");
  }
  const until = new Date(Date.now() + 30 * 86_400_000).toISOString().slice(0, 10);
  await page.getByLabel("Valid to").fill(until);
  await page.getByLabel("Total duration in days").fill("240");
  await page.getByLabel("Payment terms").fill("Stage-wise, agreed with the homeowner.");
  await axe(page);
  await page.getByRole("button", { name: "Submit quote" }).click();
  await expect(page.getByText(/v1 · STANDARD · SUBMITTED/)).toBeVisible();
  await axe(page);
}

test("a family requests contractor quotes, operations publish a neutral comparison, and the family selects one with a code", async ({
  page,
  request,
  browser,
}) => {
  test.setTimeout(600_000);
  const suffix = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 5)}`;
  const project = await projectWithPackage(page, request);
  const ownerEmail = sql(`SELECT c.normalized FROM user_contacts c JOIN projects p ON p.owner_user_id = c.user_id
    WHERE p.id = '${project.id}' AND c.is_primary`);
  await acceptedBuildPlan(page, request, project, suffix, ownerEmail);
  const alpha = `E2E Alpha ${suffix}`;
  const beta = `E2E Beta ${suffix}`;
  const pageA = await contractor(browser, request, alpha);
  const pageB = await contractor(browser, request, beta);

  // The family finds both contractors and requests quotes.
  await page.goto(`${IHB}/projects/${project.id}/quotes?q=${suffix}`);
  await expect(page.getByRole("heading", { name: "Contractor quotes" })).toBeVisible();
  await expect(page.getByText("Accepted Build Plan version 1")).toBeVisible();
  await axe(page);
  await page.getByLabel(`${alpha}, ${alpha} LLP`).check();
  await page.getByLabel(`${beta}, ${beta} LLP`).check();
  await page.getByRole("button", { name: "Request quotes" }).click();
  await expect(page.getByText("State: DRAFT")).toBeVisible();
  await axe(page);

  // Operations set the deadline and issue: the pack is frozen.
  const rfqId = sql(`SELECT id FROM rfqs WHERE project_id = '${project.id}'`);
  await page.goto(`${OPS}/rfqs`);
  await expect(page.getByRole("heading", { name: "Requests for quotation" })).toBeVisible();
  await axe(page);
  await page.goto(`${OPS}/rfqs/${rfqId}`);
  // Type only once the page is interactive: text typed before hydration is merged with the form's
  // initial JSON (seen on a cold dev-server compile).
  await page.waitForLoadState("networkidle");
  const deadline = page.locator("form").filter({ has: page.getByLabel("Set the deadline (ISO date-time)") });
  await deadline.getByLabel("Set the deadline (ISO date-time)").fill(
    JSON.stringify({ quotes_due_at: new Date(Date.now() + 7 * 86_400_000).toISOString() }),
  );
  await deadline.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText(/Quote deadline: \d{4}-/)).toBeVisible();
  await axe(page);
  await page.getByRole("button", { name: "Issue" }).click();
  await expect(page.getByRole("heading", { name: `Project ${project.code}` })).toBeVisible();
  await expect(page.getByText(/^ISSUED · /)).toBeVisible();

  // Each contractor quotes every line; one excludes it with a reason.
  await quote(pageA, false);
  await quote(pageB, true);

  // The family sees status only, never a price, before publication.
  await page.goto(`${IHB}/projects/${project.id}/quotes`);
  await expect(page.getByText("Prices appear once Plan2Build publishes the comparison.")).toBeVisible();
  await expect(page.getByText("2,250.00")).toHaveCount(0);
  await axe(page);

  // Operations review both and publish the comparison.
  await page.goto(`${OPS}/rfqs/${rfqId}`);
  for (let n = 0; n < 2; n++) {
    await page.getByRole("button", { name: "Mark reviewed" }).first().click();
    await expect(page.locator('[data-review="REVIEWED"]')).toHaveCount(n + 1);
  }
  await page.getByRole("button", { name: "Publish comparison" }).click();
  await expect(page.locator('[data-comparison="PUBLISHED"]')).toBeVisible();
  await axe(page);

  // The family reads the neutral comparison and selects Alpha's quote with a code.
  await page.goto(`${IHB}/projects/${project.id}/quotes`);
  const comparison = page.getByTestId("comparison");
  await expect(comparison).toContainText("Invited 2, quotes received 2, compared 2");
  await expect(comparison).toContainText("INR 2,250.00");
  await expect(comparison).not.toContainText(/lowest|best|recommended/i);
  await axe(page);
  const alphaQuote = comparison.locator("[data-quote]").filter({ hasText: alpha });
  const before = await codeCount(request, ownerEmail);
  await alphaQuote.getByRole("button", { name: "Select this quote" }).click();
  await expect(alphaQuote.getByText(/not a party to the construction contract/)).toBeVisible();
  await alphaQuote.getByLabel("Your name for the contractor").fill("Asha Verma");
  await alphaQuote.getByLabel("Your phone for the contractor").fill("+91 98765 43210");
  await alphaQuote.getByLabel("Confirmation code").fill(await confirmationCode(request, ownerEmail, before));
  await axe(page);
  await alphaQuote.getByRole("button", { name: "Confirm selection" }).click();
  await expect(page.getByText(new RegExp(`Selected: ${alpha}`))).toBeVisible();
  await expect(page.getByText("State: CLOSED")).toBeVisible();
  await axe(page);

  // Alpha is engaged and sees the family's contact; Beta sees only the outcome.
  await pageA.reload();
  await expect(pageA.getByText(/ACCEPTED · SELECTED/)).toBeVisible();
  // Selection creates the engagement; the invitation hands over to its Project workspace.
  await pageA.getByRole("link", { name: "Open the project workspace" }).click();
  await expect(pageA).toHaveURL(/\/engagements\/[0-9a-f-]+$/, { timeout: 30_000 });
  await expect(pageA.getByTestId("family-contact")).toContainText("Asha Verma");
  await expect(pageA.getByTestId("family-contact")).toContainText("+91 98765 43210");
  await axe(pageA);
  await pageB.reload();
  await expect(pageB.getByText(/ACCEPTED · NOT_SELECTED/)).toBeVisible();
  await expect(pageB.getByRole("link", { name: "Open the project workspace" })).toHaveCount(0);
  await axe(pageB);
  await pageA.context().close();
  await pageB.context().close();
});
