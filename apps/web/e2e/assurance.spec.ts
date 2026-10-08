// Slice 3.7B end to end (functional screens): ADMIN appoints an auditor with a professionals-site
// account; the engaged contractor asks for completion of a gate stage (through the API: the 3.7A
// spec covers that screen); operations schedule the inspection from the assurance queue; the
// auditor starts it, records a finding and submits with an emailed code; operations approve; the
// family reads the outcome, the finding and the report; the contractor submits a correction with
// a photo; operations schedule a re-inspection; the auditor passes it; operations approve and the
// finding closes. Axe on every screen, phone and desktop.
import { expect, test, type Page } from "@playwright/test";

import {
  IHB,
  OPS,
  PNG,
  PRO,
  api,
  codeCount,
  confirmationCode,
  engagedContractor,
  expectAccessible as axe,
  projectWithPackage,
  signInByCode,
  sql,
  staffReady,
  uniqueEmail,
} from "./support";

function stagePhoto(projectId: string, userId: string): string {
  return sql(`INSERT INTO file_objects (id, bucket, object_key, purpose, owner_user_id, project_id,
      original_name, declared_mime, detected_mime, size_bytes, sha256, state)
    VALUES (gen_random_uuid(), 'e2e', 'e2e/' || gen_random_uuid(), 'STAGE_EVIDENCE', '${userId}',
      '${projectId}', 'site.png', 'image/png', 'image/png', 1000,
      md5(random()::text) || md5(random()::text), 'AVAILABLE') RETURNING id;`).split("\n")[0];
}

async function inspect(auditor: Page, request: Parameters<typeof codeCount>[0], email: string, finding: boolean) {
  await auditor.goto(`${PRO}/inspections`);
  await expect(auditor.getByRole("heading", { level: 1, name: "Your inspections" })).toBeVisible();
  await axe(auditor);
  await auditor.getByTestId("assigned").filter({ hasText: "Scheduled" }).first().getByRole("link", { name: "Open" }).click();
  await auditor.getByRole("button", { name: "The stage is ready: start the inspection" }).click();
  const form = auditor.getByTestId("results-form");
  await expect(form).toBeVisible();
  if (finding) {
    const point = form.locator('fieldset[data-checkpoint="G1-A06"]');
    await point.getByLabel("Result").selectOption("NON_CONFORMANCE");
    await point.getByLabel("Severity").selectOption("MAJOR");
    await point.getByLabel("What is wrong").fill("Cover blocks missing at two column bases.");
    await point.getByLabel("Correction required").fill("Place 50 mm cover blocks before the pour.");
    await point.getByLabel("Due by").fill("2099-01-31");
  }
  await axe(auditor);
  await form.getByRole("button", { name: "Save results" }).click();
  await expect(auditor.getByText("Results saved.")).toBeVisible({ timeout: 30_000 });
  const before = await codeCount(request, email);
  await auditor.getByRole("button", { name: "Email me a code to submit" }).click();
  await auditor.getByLabel("Code").fill(await confirmationCode(request, email, before));
  await axe(auditor);
  await auditor.getByRole("button", { name: "Submit the inspection" }).click();
  await expect(auditor.getByText(/Submitted, awaiting approval/)).toBeVisible();
}

test("an auditor's finding is approved, corrected by the contractor and closed by a re-inspection", async ({
  page,
  request,
  browser,
}) => {
  test.setTimeout(900_000);
  const suffix = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 5)}`;
  const project = await projectWithPackage(page, request);
  const { pro, engagementId, userId } = await engagedContractor(page, request, browser, project.id, `E2E Builder ${suffix}`);

  // The auditor's account, and ADMIN's appointment.
  const auditor = await (await browser.newContext()).newPage();
  const auditorEmail = uniqueEmail();
  await auditor.goto(`${PRO}/sign-in`);
  await signInByCode(auditor, request, auditorEmail);
  await expect(auditor.getByLabel("Your professional identity")).toBeVisible({ timeout: 30_000 });
  const admin = await (await browser.newContext()).newPage();
  await staffReady(admin, request, false, "ADMIN");
  const appointment = await api(admin, OPS, "POST", "/api/v1/admin/auditor-appointments", {
    name: `E2E Auditor ${suffix}`, qualification: "Chartered civil engineer (TEST)", account_email: auditorEmail,
  });
  const appointmentId = appointment.id as string;
  await admin.goto(`${OPS}/assurance/config`);
  await expect(admin.getByRole("heading", { level: 1, name: "Auditors and checklists" })).toBeVisible();
  await axe(admin);

  // The contractor asks for completion of stage 3, a gate stage.
  const stage3 = sql(`SELECT id FROM stage_instances WHERE project_id = '${project.id}' AND stage_number = 3`);
  for (const kind of ["PROGRESS", "COMPLETION_REQUEST"]) {
    await api(pro, PRO, "POST", `/api/v1/pro/engagements/${engagementId}/stages/${stage3}/updates`, {
      kind, note: "Footings ready for the pour.", file_ids: [stagePhoto(project.id, userId)],
    });
  }

  // Operations schedule it from the queue.
  await page.goto(`${OPS}/assurance`);
  await expect(page.getByRole("heading", { level: 1, name: "Assurance" })).toBeVisible();
  const card = page.getByTestId("to-schedule").filter({ hasText: project.code });
  await expect(card).toBeVisible();
  await axe(page);
  await card.getByLabel("Schedule (JSON: appointment_id, visit_note)").fill(
    JSON.stringify({ appointment_id: appointmentId, visit_note: "Tuesday 10:00" }),
  );
  await card.getByRole("button", { name: "Send" }).click();
  await expect(page.getByTestId("to-schedule").filter({ hasText: project.code })).toHaveCount(0);

  // The auditor records a finding and submits with a code; operations approve.
  await inspect(auditor, request, auditorEmail, true);
  await page.goto(`${OPS}/assurance/${project.id}`);
  await axe(page);
  await page.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByTestId("inspection-state").first()).toHaveText("Approved");

  // The family reads the outcome, the finding and the report.
  await page.goto(`${IHB}/projects/${project.id}/construction`);
  await expect(page.getByTestId("inspection-outcome").first()).toContainText("need correction");
  await expect(page.getByTestId("finding")).toContainText("Cover blocks missing");
  await expect(page.getByRole("button", { name: "Report version 1" })).toBeVisible();
  await expect(page.getByTestId("stage-3-x")).toContainText("findings open");
  await axe(page);

  // The contractor submits its correction with a photo.
  await pro.goto(`${PRO}/engagements/${engagementId}/execution`);
  const rectify = pro.getByTestId("rectify-form");
  await rectify.getByLabel("What was corrected").fill("Cover blocks placed at every column base.");
  await rectify.getByLabel(/Photos of the correction/).setInputFiles({ name: "fixed.png", mimeType: "image/png", buffer: PNG });
  await axe(pro);
  await rectify.getByRole("button", { name: "Submit the correction" }).click();
  // The form goes once the finding leaves OPEN; the finding shows the new state.
  await expect(pro.getByTestId("finding")).toContainText("Correction submitted", { timeout: 60_000 });
  await axe(pro);

  // Operations schedule the re-inspection; the auditor passes it; operations approve.
  const ncId = sql(`SELECT id FROM non_conformances WHERE project_id = '${project.id}'`);
  await page.goto(`${OPS}/assurance/${project.id}`);
  const finding = page.getByTestId("ops-finding");
  const reinspect = finding.locator("form").filter({
    has: page.getByLabel("Schedule a re-inspection (JSON: nc_ids, appointment_id)"),
  });
  await reinspect.getByLabel("Schedule a re-inspection (JSON: nc_ids, appointment_id)").fill(
    JSON.stringify({ nc_ids: [ncId], appointment_id: appointmentId }),
  );
  await reinspect.getByRole("button", { name: "Send" }).click();
  await expect(finding).toContainText("Re-inspection scheduled");
  await inspect(auditor, request, auditorEmail, false);
  await page.goto(`${OPS}/assurance/${project.id}`);
  await page.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByTestId("ops-finding")).toContainText("Closed by re-inspection");
  await axe(page);
  await page.goto(`${IHB}/projects/${project.id}/construction`);
  await expect(page.getByTestId("finding")).toContainText("Closed by re-inspection");
  await expect(page.getByTestId("stage-3-x")).toContainText("cleared");
  await axe(page);
  for (const p of [pro, auditor, admin]) await p.context().close();
});
