// Slice 3.3 billing end to end, with the fake gateway and the local stack's TEST configuration
// (python -m p2b.billing.seed_dev): the eligibility checklist on acceptance, the package price
// from the server, an order, a failed and then a successful payment through the development
// checkout (whose callback is only a hint the server verifies), the package active with the
// project unchanged, the invoice, a refund request decided by operations, buying an AI credit
// and spending it only by choice, the operations billing screens and ADMIN configuration. Axe on
// every screen, phone and desktop.
import { expect, test, type Page } from "@playwright/test";

import {
  IHB,
  OPS,
  acceptWithChecklist,
  animationsDone,
  expectAccessible as axe,
  sql,
  staffReady,
  submitRequirement,
  workerContainer,
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

/** A submitted project accepted with the checklist by a fresh OPS reviewer. */
async function acceptedProject(page: Page, request: Parameters<typeof submitRequirement>[1]) {
  const project = await submitRequirement(page, request);
  await staffReady(page, request);
  await openFromQueue(page, project.code);
  await page.getByRole("button", { name: "Claim for review" }).click();
  await acceptWithChecklist(page);
  return project;
}

async function buyerDetails(page: Page) {
  await page.getByLabel("Name on the invoice").fill("Asha Verma");
  await page.getByLabel("Billing address").fill("12 Civil Lines, Raipur");
  await page.getByLabel("State").selectOption({ label: "Chhattisgarh" });
  await page.getByLabel(/I accept the purchase and refund terms/).check();
}

async function payInTestCheckout(page: Page, outcome: "Pay (test)" | "Fail the payment (test)") {
  await page.getByRole("button", { name: /^Pay ₹/ }).click();
  const checkout = page.getByRole("dialog", { name: "Test payment" });
  await expect(checkout.getByText("Development checkout: no real payment provider and no money.")).toBeVisible();
  await animationsDone(checkout);
  await axe(page);
  await checkout.getByRole("button", { name: outcome }).click();
}

async function orderPackage(page: Page, project: Submitted) {
  await page.goto(`${IHB}/projects/${project.id}/package`);
  await expect(page.getByRole("heading", { name: "Plan2Build package" })).toBeVisible();
  await expect(page.getByText("Development values: this is not a real price, and no real money moves.")).toBeVisible();
  await expect(page.getByText("Status: Not active")).toBeVisible();
  await axe(page);
  await page.getByText("In full now").click();
  await buyerDetails(page);
  await page.getByRole("button", { name: "Continue to payment" }).click();
  await expect(page).toHaveURL(/\/package\/orders\/[0-9a-f-]+$/);
  await expect(page.getByText("Status: Awaiting payment")).toBeVisible();
}

test("a family buys the package: a failed payment, then a verified one; the package is active and nothing else moves", async ({
  page,
  request,
}) => {
  test.setTimeout(240_000);
  const project = await acceptedProject(page, request);

  // The overview's next step offers the package once the review is complete.
  await page.goto(`${IHB}/projects/${project.id}`);
  await page.getByRole("link", { name: "See what it includes" }).click();
  await orderPackage(page, project);
  await axe(page);

  await payInTestCheckout(page, "Fail the payment (test)");
  await expect(page.getByText(/The last payment did not go through\. No money was taken/)).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Status: Awaiting payment")).toBeVisible();

  await payInTestCheckout(page, "Pay (test)");
  await expect(page.getByText("Status: Paid")).toBeVisible({ timeout: 45_000 });
  await expect(page.getByRole("button", { name: /^Download TEST\// })).toBeVisible({ timeout: 45_000 });
  await axe(page);

  // The package is active; the project's status is unchanged (L-06).
  await page.goto(`${IHB}/projects/${project.id}`);
  await expect(page.getByRole("region", { name: "Your project" }).getByText("Active", { exact: true })).toBeVisible();
  await expect(page.getByText("Status: Accepted")).toBeVisible();
  await page.goto(`${IHB}/projects/${project.id}/package`);
  await expect(page.getByText("Status: Active")).toBeVisible();
  await expect(page.getByRole("button", { name: "Continue to payment" })).toHaveCount(0);
  await axe(page);

  // A refund request, decided by operations with a reason.
  await page.getByRole("link", { name: /^ORD-/ }).first().click();
  const heading = (await page.getByRole("heading", { name: /^Order ORD-/ }).textContent()) ?? "";
  const code = heading.replace("Order ", "");
  await page.getByRole("button", { name: "Request a refund" }).click();
  await page.getByLabel("Why would you like a refund?").fill("Our plans changed.");
  await animationsDone(page.getByRole("dialog", { name: "Request a refund" }));
  await axe(page);
  await page.getByRole("button", { name: "Send request" }).click();
  await expect(page.getByText("Status: Requested").or(page.getByText("Requested", { exact: true }))).toBeVisible();

  // The reviewer who accepted the project is still signed in on the admin host.
  await page.goto(`${OPS}/billing`);
  await expect(page.getByRole("heading", { name: "Refund requests waiting" })).toBeVisible();
  await axe(page);
  await page.getByRole("link", { name: `Refund request · ${code}` }).click();
  await expect(page.getByText("No package service delivered yet.")).toBeVisible();
  await page.getByLabel("End the package").check();
  await page.getByLabel("Reason (the family sees it)").fill("Before any package service was used.");
  await axe(page);
  await page.getByRole("button", { name: "Approve refund" }).click();
  await expect(page.getByText(/Status: (Approved|Refunded)/)).toBeVisible();

  await page.goto(`${IHB}/projects/${project.id}/package`);
  await expect(page.getByText("Status: Refunded")).toBeVisible();
  await expect(page.getByText("This package is no longer active.")).toBeVisible();
});

test("an AI credit is bought, spent only by choice, and returned once when a paid design fails", async ({ page, request }) => {
  test.setTimeout(240_000);
  const project = await acceptedProject(page, request);

  await page.goto(`${IHB}/account/ai-credits/buy?project=${project.id}`);
  await expect(page.getByRole("heading", { name: "Buy 1 AI credit", level: 1 })).toBeVisible();
  await expect(page.getByText("No AI credits")).toBeVisible();
  await axe(page);
  await buyerDetails(page);
  await page.getByRole("button", { name: "Buy 1 AI credit" }).click();
  await expect(page).toHaveURL(/\/account\/orders\/[0-9a-f-]+\?project=/);
  await payInTestCheckout(page, "Pay (test)");
  await expect(page.getByText("Status: Paid")).toBeVisible({ timeout: 45_000 });
  await axe(page);

  await page.goto(`${IHB}/account/billing`);
  await expect(page.getByText("1 AI credit", { exact: true })).toBeVisible();
  await axe(page);

  // Use the three free designs, then spend the credit only through "Use 1 AI credit".
  await page.goto(`${IHB}/projects/${project.id}/designs`);
  const generate = page.getByRole("button", { name: "Generate My Design" });
  for (const left of ["2", "1", "0"]) {
    await generate.click();
    await expect(page.getByTestId("free-remaining")).toHaveText(`${left} of 3 free designs left`, { timeout: 45_000 });
    await expect(page.getByText(/designs? (is|are) being generated/)).toHaveCount(0, { timeout: 45_000 });
  }
  await expect(page.getByTestId("credit-balance")).toHaveText("1 AI credit");
  await expect(generate).toBeDisabled();
  await axe(page);
  const returns = () =>
    sql(
      "SELECT count(*) FROM ai_credit_ledger l JOIN design_generations g ON g.id = l.generation_id " +
        `WHERE g.project_id = '${project.id}' AND l.entry = 'RETURN'`,
    );

  // A paid generation that fails gives its credit back, once. The demo provider never fails, so
  // the worker is held while the request waits, and the request is aged past the stale limit:
  // the next read expires it as failed and returns the credit.
  workerContainer("pause");
  try {
    await page.getByRole("button", { name: "Use 1 AI credit" }).click();
    await expect(page.getByTestId("credit-balance")).toHaveText("No AI credits", { timeout: 45_000 });
    sql(
      "UPDATE design_generations SET created_at = now() - interval '2 days' " +
        `WHERE project_id = '${project.id}' AND funding = 'PAID' AND state IN ('QUEUED', 'RUNNING')`,
    );
    await page.reload();
    await expect(page.getByTestId("credit-balance")).toHaveText("1 AI credit");
    await expect(page.getByText("The request was not completed.")).toBeVisible();
  } finally {
    workerContainer("unpause");
  }
  expect(returns()).toBe("1");
  await axe(page);

  // The returned credit is spent again, by choice, and this time the design is made.
  await page.getByRole("button", { name: "Use 1 AI credit" }).click();
  await expect(page.getByTestId("credit-balance")).toHaveText("No AI credits", { timeout: 45_000 });
  const gallery = page.getByRole("list", { name: "Designs" });
  await expect(gallery.getByRole("img", { name: /design 5\. Illustrative concept\.$/ })).toBeVisible({
    timeout: 45_000,
  });
  // The held job, now running, finds its request already failed: nothing is returned twice.
  await page.reload();
  await expect(page.getByTestId("credit-balance")).toHaveText("No AI credits");
  expect(returns()).toBe("1");
  await expect(page.getByRole("link", { name: "Buy 1 AI credit" })).toBeVisible();
  await axe(page);
});

test("operations and ADMIN billing screens", async ({ page, request }) => {
  test.setTimeout(120_000);
  await staffReady(page, request, false, "ADMIN");
  await page.goto(`${OPS}/admin/billing`);
  await expect(page.getByRole("heading", { name: "Billing configuration" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Pricing rules" })).toBeVisible();
  await expect(page.getByText("TEST").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Eligibility checklist" })).toBeVisible();
  await axe(page);
  await page.goto(`${OPS}/billing`);
  await expect(page.getByRole("heading", { name: "Billing", level: 1 })).toBeVisible();
  await axe(page);
  await page.goto(`${OPS}/billing/exceptions`);
  await expect(page.getByRole("heading", { name: "Payment exceptions", level: 1 })).toBeVisible();
  await axe(page);
});
