// Slice 3.7C end to end (functional screens): with the final snag gate cleared (seeded here; the
// assurance spec covers inspections), operations open the handover; the contractor adds a warranty
// document and its warranty; operations confirm it ready; the owner reads the statement and
// acknowledges with an emailed code; operations issue the Build Record; the owner sees the version
// with its PDF and data file. Axe on every screen, phone and desktop.
import { expect, test } from "@playwright/test";

import {
  IHB,
  OPS,
  PNG,
  PRO,
  codeCount,
  confirmationCode,
  engagedContractor,
  expectAccessible as axe,
  projectWithPackage,
  sql,
} from "./support";

test("the owner acknowledges the handover with a code and receives the issued Build Record", async ({
  page,
  request,
  browser,
}) => {
  test.setTimeout(600_000);
  const suffix = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 5)}`;
  const project = await projectWithPackage(page, request);
  const { pro, engagementId } = await engagedContractor(page, request, browser, project.id, `E2E Builder ${suffix}`);
  sql(`UPDATE stage_instances SET gate_status = 'CLEARED'
       WHERE project_id = '${project.id}' AND stage_number = 16;`);
  const ownerEmail = sql(`SELECT c.normalized FROM user_contacts c JOIN projects p ON p.owner_user_id = c.user_id
    WHERE p.id = '${project.id}' AND c.is_primary`);

  // Operations open the handover.
  await page.goto(`${OPS}/handover/${project.id}`);
  await page.getByRole("button", { name: "Open the handover" }).click();
  await expect(page.getByTestId("handover-state")).toHaveText("Open: documents are being recorded");
  await axe(page);

  // The contractor adds a warranty document and its warranty.
  await pro.goto(`${PRO}/engagements/${engagementId}/execution`);
  const documentForm = pro.getByTestId("handover-document-form");
  await documentForm.getByLabel("Kind").selectOption("WARRANTY");
  await documentForm.getByLabel("Title").fill("Waterproofing warranty");
  await documentForm.getByLabel(/^File/).setInputFiles({ name: "warranty.png", mimeType: "image/png", buffer: PNG });
  await axe(pro);
  await documentForm.getByRole("button", { name: "Add" }).click();
  await expect(pro.getByText("Warranty: Waterproofing warranty")).toBeVisible({ timeout: 60_000 });
  const warrantyForm = pro.getByTestId("warranty-form");
  await warrantyForm.getByLabel("Item").fill("Terrace waterproofing");
  await warrantyForm.getByLabel("Term").fill("5 years");
  await warrantyForm.getByLabel("Installer").fill("Dry Roofs (TEST)");
  await warrantyForm.getByLabel("Expiry date").fill("2031-10-01");
  await warrantyForm.getByRole("button", { name: "Add a warranty" }).click();
  await expect(pro.getByText(/Terrace waterproofing: 5 years/)).toBeVisible();
  await axe(pro);

  // Operations confirm it ready.
  await page.goto(`${OPS}/handover/${project.id}`);
  await page.getByRole("button", { name: "Confirm the documents are recorded" }).click();
  await expect(page.getByTestId("handover-state")).toHaveText("Ready for your acknowledgement");

  // The owner reads the statement and acknowledges with the code.
  await page.goto(`${IHB}/projects/${project.id}/construction`);
  await expect(page.getByTestId("handover-state")).toHaveText("Ready for your acknowledgement");
  await axe(page);
  const before = await codeCount(request, ownerEmail);
  await page.getByRole("button", { name: "Email me a code to acknowledge" }).click();
  await expect(page.getByTestId("statement")).toContainText("not a completion certificate");
  await page.getByLabel("Code").fill(await confirmationCode(request, ownerEmail, before));
  await axe(page);
  await page.getByRole("button", { name: "Acknowledge the handover" }).click();
  await expect(page.getByTestId("handover-state")).toHaveText("Acknowledged by the owner");
  await expect(page.getByText("No Build Record is issued yet.")).toBeVisible();

  // Operations issue the Build Record; the owner sees version 1 with its PDF and data file.
  await page.goto(`${OPS}/handover/${project.id}`);
  await expect(page.getByTestId("ops-build-record")).toContainText("Version 1 · draft · ACKNOWLEDGED");
  await page.getByRole("button", { name: "Issue version 1" }).click();
  await expect(page.getByTestId("ops-build-record")).toContainText("Version 1 · current");
  await axe(page);
  await page.goto(`${IHB}/projects/${project.id}/construction`);
  const version = page.getByTestId("build-record-version");
  await expect(version).toContainText("Version 1 · current");
  await expect(version.getByRole("button", { name: "PDF, version 1" })).toBeVisible();
  await expect(version.getByRole("button", { name: "Data file, version 1" })).toBeVisible();
  await axe(page);
  await pro.context().close();
});
