// Operations review end to end, on the admin host with the family's view on the homeowner host:
// staff accounts made by the server command, emailed-code sign-in, TOTP setup, the review queue
// (fed by the worker through the outbox), claim and release, and the three decisions: accept
// (the family then sees the workspace), request information (the family revises and resubmits)
// and cancel (the family sees the reason; nothing can be accepted after). Axe on every screen.
import { expect, test, type Page } from "@playwright/test";

import {
  IHB,
  OPS,
  expectAccessible as axe,
  signInByCode,
  acceptWithChecklist,
  staffReady,
  submitRequirement,
  totp,
  openSection,
} from "./support";

/** Open a project from the queue, waiting for the worker to deliver it there. The queue is
 * oldest first, so a new submission can sit on a later page. */
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
  await expect(page.getByRole("heading", { level: 1, name: `Project ${code}` })).toBeVisible();
}

async function claim(page: Page) {
  await page.getByRole("button", { name: "Claim for review" }).click();
  await expect(page.getByText("You are reviewing this submission.")).toBeVisible();
}

test("operations staff set up MFA, find a submission in the queue, and claim it", async ({
  browser,
  page,
  request,
}) => {
  test.setTimeout(120_000);
  const project = await submitRequirement(page, request);
  const { email, secret } = await staffReady(page, request, true);

  await openFromQueue(page, project.code);
  const row = page.getByRole("row").filter({ has: page.getByRole("link", { name: project.code }) });
  await page.goBack(); // the queue page that lists it
  await expect(row.getByText("Other property type")).toBeVisible();
  await expect(page).toHaveTitle("Review queue | Plan2Build");
  await axe(page);

  await openFromQueue(page, project.code);
  await expect(page.getByText("Status: Submitted")).toBeVisible();
  await expect(page.getByText("A small hostel")).toBeVisible();
  await expect(page.getByText("Claim the submission to decide on it.")).toBeVisible();
  await axe(page);
  await claim(page);
  await axe(page);
  await page.getByRole("button", { name: "Release" }).click();
  await expect(page.getByText("Nobody is reviewing this submission yet.")).toBeVisible();

  // A new session needs the authenticator code; a wrong one is refused readably.
  const { viewport, userAgent, isMobile, hasTouch, deviceScaleFactor } = test.info().project.use;
  const fresh = await browser.newContext({ viewport, userAgent, isMobile, hasTouch, deviceScaleFactor });
  const again = await fresh.newPage();
  await again.goto(`${OPS}/queue`);
  await signInByCode(again, request, email, 1);
  await expect(again).toHaveURL(/\/mfa(\?|$)/, { timeout: 30_000 });
  await axe(again);
  await again.getByLabel("Authenticator code or recovery code").fill("000000");
  await again.getByRole("button", { name: "Verify" }).click();
  if (totp(secret) !== "000000") {
    await expect(again.getByRole("main").getByRole("alert")).toHaveText(/That code is not valid/);
  }
  await again.getByLabel("Authenticator code or recovery code").fill(totp(secret, 1));
  await again.getByRole("button", { name: "Verify" }).click();
  await expect(again).toHaveURL(`${OPS}/queue`);
  await fresh.close();
});

test("accepting completes the initial review; the family sees stages and specification", async ({ page, request }) => {
  test.setTimeout(120_000);
  const project = await submitRequirement(page, request);
  await staffReady(page, request);
  await openFromQueue(page, project.code);
  await claim(page);

  await acceptWithChecklist(page, () => axe(page));
  await expect(page.getByRole("button", { name: "Accept" })).toHaveCount(0);
  // The recorded checklist (F-05) is shown with the decision.
  await expect(page.getByRole("heading", { name: "Eligibility checklist" })).toBeVisible();
  await expect(page.getByText("New individual house: Passed")).toBeVisible();
  await axe(page);

  // The same browser holds the family's session on the homeowner host.
  await page.goto(`${IHB}/projects/${project.id}`);
  await expect(page.getByText("Status: Accepted")).toBeVisible();
  // ACCEPTED is the initial review only; the package can now be offered (L-02).
  await expect(page.getByText("Plan2Build's initial review is complete")).toBeVisible();
  await expect(page.getByText(/does not approve your design, your budget or any professional/)).toBeVisible();
  await expect(page.getByRole("link", { name: "View the package" })).toBeVisible();
  await expect(page.getByRole("button", { name: /buy|pay/i })).toHaveCount(0);
  await axe(page);

  await openSection(page, "Construction stages");
  // G+1 with a basement: 13 stages once, stages 5, 6 and 9 for basement, ground and first floor.
  // Slice 3.7A: the page shows what happened on each stage; no planned dates (EX-04, BP-07A).
  const stages = page.locator('[data-testid^="stage-"]').filter({ has: page.getByTestId("stage-state") });
  await expect(stages).toHaveCount(13 + 3 * 3);
  await expect(page.getByText(/Basement/).first()).toBeVisible();
  await expect(page.getByTestId("stage-state").first()).toHaveText("Not started");
  await axe(page);

  await openSection(page, "Specification");
  await expect(page.getByRole("heading", { name: "Group A: Structure" })).toBeVisible();
  await expect(page.getByText(/Package [ABC]/)).toHaveCount(0); // groups, never products (PD-09)
  await expect(page.getByText("Soil investigation")).toBeVisible();
  await expect(
    page.getByText("The criteria for each decision appear here once your Plan2Build package is active."),
  ).toHaveCount(1);
  await expect(page.getByText("Bearing capacity")).toHaveCount(0); // criteria hidden (F-09 setting)
  await expect(page.getByText("Engineer sign-off pending")).toHaveCount(8); // structural lines (2.4)
  await axe(page);
});

test("asking for information lets the family revise and resubmit; cancelling is final", async ({
  page,
  request,
}) => {
  test.setTimeout(180_000);
  const project = await submitRequirement(page, request);
  await staffReady(page, request);
  await openFromQueue(page, project.code);
  await claim(page);

  // A message is required.
  await page.getByRole("button", { name: "Request information" }).click();
  const askDialog = page.getByRole("dialog", { name: "Request more information" });
  await askDialog.getByRole("button", { name: "Send request" }).click();
  await expect(askDialog.getByText("Write a message first.")).toBeVisible();
  await axe(page);
  await askDialog.getByLabel("Message to the family").fill("Please add the plot's survey number.");
  await askDialog.getByRole("button", { name: "Send request" }).click();
  await expect(page.getByText("Status: Needs information")).toBeVisible();

  // The family sees the message, updates the requirement and submits again.
  await page.goto(`${IHB}/projects/${project.id}`);
  await expect(page.getByText("Please add the plot's survey number.")).toBeVisible();
  await expect(page.getByText("Other property type")).toHaveCount(0); // flags stay internal
  await axe(page);
  await page.getByRole("link", { name: "Update your requirement" }).click();
  await expect(page.getByText("Please add the plot's survey number.")).toBeVisible();
  for (const step of ["Your plot", "Your house", "Budget and timing", "What matters most"]) {
    await expect(page.getByRole("heading", { name: step, exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Save and continue" }).click();
  }
  await page.getByLabel("Anything else we should know?").fill("Survey number 12/4.");
  await page.getByRole("button", { name: "Save and continue" }).click();
  await page.getByRole("button", { name: "Submit my requirement" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Submit", exact: true }).click();
  await expect(page).toHaveURL(`${IHB}/projects/${project.id}`);
  await expect(page.getByText("Status: Submitted")).toBeVisible();

  // Back in the queue; operations cancel with a reason.
  await openFromQueue(page, project.code);
  await expect(page.getByText("Survey number 12/4.")).toBeVisible();
  await claim(page);
  await page.getByRole("button", { name: "Cancel project" }).click();
  const cancelDialog = page.getByRole("dialog", { name: "Cancel this project" });
  await cancelDialog.getByLabel("Reason").fill("The plot is outside the area we serve.");
  await axe(page);
  await cancelDialog.getByRole("button", { name: "Cancel project" }).click();
  await expect(page.getByText("Status: Cancelled")).toBeVisible();
  await expect(page.getByRole("button", { name: "Accept" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Cancel project" })).toHaveCount(0);
  await axe(page);

  await page.goto(`${IHB}/projects/${project.id}`);
  await expect(page.getByText("This project has been closed", { exact: true })).toBeVisible();
  await expect(page.getByText("Reason: The plot is outside the area we serve.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Update your requirement" })).toHaveCount(0);
  await axe(page);
});

test("operations pages exist only on the admin host", async ({ page }) => {
  expect((await page.goto(`${IHB}/queue`))?.status()).toBe(404);
  expect((await page.goto(`${OPS}/estimate`))?.status()).toBe(404);
});
