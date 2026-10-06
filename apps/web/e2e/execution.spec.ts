// Slice 3.7A end to end (functional screens): a family with the package engages a listed
// contractor (connection sent and accepted through the API: the 3.4 spec covers those screens).
// The contractor opens the construction execution page from its engagement, posts a progress
// update with a photo (uploaded, scanned and re-encoded by the worker) and then a completion
// request; the family reads the update, confirms completion and marks the milestone paid; the
// contractor marks it received; operations see the queue and the project. No dates or
// percentages appear anywhere. Axe on every screen, phone and desktop.
import { expect, test } from "@playwright/test";

import {
  IHB,
  OPS,
  PNG,
  PRO,
  engagedContractor,
  expectAccessible as axe,
  projectWithPackage,
} from "./support";

test("a contractor reports a stage, the family confirms it and marks the payment, operations see it", async ({
  page,
  request,
  browser,
}) => {
  test.setTimeout(600_000);
  const suffix = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 5)}`;
  const project = await projectWithPackage(page, request);
  const name = `E2E Builder ${suffix}`;
  const { pro, engagementId } = await engagedContractor(page, request, browser, project.id, name);

  // The contractor posts a progress update with a photo, then a completion request.
  await pro.goto(`${PRO}/engagements/${engagementId}`);
  await pro.getByRole("link", { name: "Construction execution" }).click();
  await expect(pro.getByRole("heading", { level: 1, name: "Construction execution" })).toBeVisible();
  await expect(pro.getByText(/%/)).toHaveCount(0);
  await axe(pro);
  const form = pro.getByTestId("update-form");
  await form.getByLabel("Note").fill("Site cleared and marked out.");
  await form.getByLabel("Materials used (optional)").fill("Lime for marking");
  await form.getByLabel(/^Photos/).setInputFiles({ name: "site.png", mimeType: "image/png", buffer: PNG });
  await form.getByRole("button", { name: "Post update" }).click();
  await expect(pro.getByText("Update posted.")).toBeVisible({ timeout: 60_000 });
  const first = pro.getByTestId("pro-stage-1-x");
  await expect(first.getByTestId("stage-state")).toHaveText("In progress");
  await expect(first).toContainText("1 updates");
  await form.getByLabel("Update type").selectOption("COMPLETION_REQUEST");
  await form.getByLabel("Note").fill("Stage complete, please confirm.");
  await form.getByLabel(/^Photos/).setInputFiles({ name: "done.png", mimeType: "image/png", buffer: PNG });
  await form.getByRole("button", { name: "Post update" }).click();
  await expect(first.getByTestId("stage-state")).toHaveText("Completion requested", { timeout: 60_000 });
  await axe(pro);

  // The family reads the updates, confirms completion and marks the milestone paid.
  await page.goto(`${IHB}/projects/${project.id}/construction`);
  await expect(page.getByRole("heading", { name: "Construction progress" })).toBeVisible();
  await expect(page.getByTestId("contractor")).toContainText(name);
  const familyStage = page.getByTestId("stage-1-x");
  await expect(familyStage.getByTestId("stage-state")).toHaveText("Completion requested");
  await expect(page.getByText(/%/)).toHaveCount(0);
  await axe(page);
  await familyStage.getByRole("link", { name: /Updates/ }).click();
  await expect(page.getByTestId("update")).toHaveCount(2);
  await expect(page.getByTestId("update").last()).toContainText("Lime for marking");
  await expect(page.getByRole("button", { name: "Photo 1" }).first()).toBeVisible();
  await axe(page);
  await page.getByRole("link", { name: "Back to the stages" }).click();
  await familyStage.getByRole("button", { name: "Confirm completion" }).click();
  await expect(familyStage.getByTestId("stage-state")).toHaveText("Completed");
  const milestone = page.getByTestId("milestone").first(); // stage 1 is the first milestone
  await expect(milestone).toContainText("stage complete");
  await milestone.getByRole("button", { name: "Mark paid" }).click();
  await expect(milestone).toContainText("Paid (owner's mark): yes");
  await axe(page);

  // The contractor marks it received.
  await pro.reload();
  await expect(first.getByTestId("stage-state")).toHaveText("Completed");
  const proMilestone = pro.locator("li").filter({ hasText: "Paid (owner's mark): yes" }).first();
  await proMilestone.getByRole("button", { name: "Mark received" }).click();
  await expect(proMilestone).toContainText("Received (contractor's mark): yes");
  await axe(pro);

  // Operations (signed in while preparing the project) see the queue and the project.
  await page.goto(`${OPS}/execution`);
  await expect(page.getByRole("heading", { name: "Execution" })).toBeVisible();
  await axe(page);
  await page.goto(`${OPS}/execution/${project.id}`);
  await expect(page.getByTestId("ops-stage-1-x").getByTestId("stage-state")).toHaveText("Completed");
  await axe(page);
  await pro.context().close();
});
