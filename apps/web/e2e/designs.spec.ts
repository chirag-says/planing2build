// AI design concepts end to end (Slice 3.1), with the local stack's demo image provider: the
// overview entry, Generate My Design, waiting and generating, the gallery with "Illustrative"
// marks, a failed generation that uses no free design and can be tried again, the free quota
// running out, the design detail and "Use as design reference". Axe on every screen.
import { expect, test } from "@playwright/test";

import { IHB, expectAccessible as axe, sql, submitRequirement } from "./support";

test("generate designs, see the gallery, run out of free designs, mark a reference", async ({
  page,
  request,
}) => {
  test.setTimeout(180_000);
  const project = await submitRequirement(page, request);
  const base = `${IHB}/projects/${project.id}`;

  // Overview: the way in, with the free count.
  await page.goto(base);
  await expect(page.getByRole("heading", { name: "Your designs" })).toBeVisible();
  await expect(page.getByText("3 of 3 free designs left")).toBeVisible();
  await axe(page);
  await page.getByRole("link", { name: "Generate My Design" }).click();
  await expect(page).toHaveURL(`${base}/designs`);
  await expect(page).toHaveTitle(/^Designs · Project P2B-RPR-\d+ \| Plan2Build$/);
  const sections = page.getByRole("navigation", { name: "Project sections" });
  await expect(sections.getByRole("link", { name: "Designs" })).toHaveAttribute("aria-current", "page");
  await expect(page.getByText("No designs yet")).toBeVisible();
  await axe(page);

  // First design: waiting, then ready with its marks.
  const generate = page.getByRole("button", { name: "Generate My Design" });
  await generate.click();
  await expect(page.getByText("1 design is being generated.")).toBeVisible();
  const gallery = page.getByRole("list", { name: "Designs" });
  await expect(gallery.getByRole("listitem")).toHaveCount(1);
  await axe(page);
  const first = gallery.getByRole("img", { name: /^Exterior concept, design 1\. Illustrative concept\.$/ });
  await expect(first).toBeVisible({ timeout: 45_000 });
  await expect(page.getByTestId("free-remaining")).toHaveText("2 of 3 free designs left");
  await expect(gallery.getByText("Illustrative")).toHaveCount(1);
  await expect(gallery.getByText("Ready")).toBeVisible();
  expect(await first.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0);
  await axe(page);

  // A failed generation (seeded: the demo provider never fails) uses no free design.
  sql(`INSERT INTO design_generations (id, project_id, sequence, view, funding, free_quota, state,
         provider, model, prompt_template_id, prompt_template_version, question_set_version,
         requirement_version, snapshot, provider_request, failure_reason, attempts, requested_by,
         completed_at)
       SELECT gen_random_uuid(), project_id, 2, 'INTERIOR', 'FREE', free_quota, 'FAILED', provider,
         model, prompt_template_id, prompt_template_version, question_set_version,
         requirement_version, snapshot, provider_request, 'PROVIDER_TIMEOUT', 2, requested_by, now()
       FROM design_generations WHERE project_id = '${project.id}' AND sequence = 1;`);
  await page.reload();
  await expect(page.getByText(/The image service took too long\. This design could not be generated\. It did not use one of your free designs\./)).toBeVisible();
  await expect(page.getByTestId("free-remaining")).toHaveText("2 of 3 free designs left");
  await expect(gallery.getByText("Not generated")).toBeVisible();
  await axe(page);
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(gallery.getByRole("img", { name: /design 3\. Illustrative concept\.$/ })).toBeVisible({ timeout: 45_000 });
  await expect(page.getByTestId("free-remaining")).toHaveText("1 of 3 free designs left");

  // An inside view, then the free designs are used up.
  await page.getByText("Inside: the living room").click();
  await generate.click();
  await expect(gallery.getByRole("img", { name: /^Interior concept, design 4\./ })).toBeVisible({ timeout: 45_000 });
  await expect(page.getByTestId("free-remaining")).toHaveText("0 of 3 free designs left");
  await expect(generate).toBeDisabled();
  await expect(
    page.getByText("You have used your free designs for this project. You can use an AI credit for another."),
  ).toBeVisible();
  // Never silently: with no credit, the way on is to buy one (billing.spec covers spending it).
  await expect(page.getByTestId("credit-balance")).toHaveText("No AI credits");
  await expect(page.getByRole("link", { name: "Buy 1 AI credit" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Try again" })).toHaveCount(0);
  await axe(page);

  // The detail: illustrative warning, what the family may know, and a reference.
  await gallery.getByRole("link", { name: "Design 1 · Exterior concept" }).click();
  await expect(page).toHaveURL(/\/designs\/[0-9a-f-]+$/);
  await expect(sections.getByRole("link", { name: "Designs" })).toHaveAttribute("aria-current", "page");
  await expect(page.getByText("An illustrative concept only")).toBeVisible();
  await expect(page.getByText(/not a drawing, a plan, a structural design or an approved design/)).toBeVisible();
  await expect(page.getByRole("img", { name: /design 1\. Illustrative concept\.$/ })).toBeVisible();
  await expect(page.getByText("Outside of the house")).toBeVisible();
  await expect(page.getByText(/demo|provider|prompt/i)).toHaveCount(0);
  await axe(page);
  await page.getByRole("button", { name: "Use as design reference" }).click();
  await expect(page.getByText(/^Marked as a design reference on /)).toBeVisible();
  await expect(page.getByRole("button", { name: "Use as design reference" })).toHaveCount(0);
  await axe(page);
  // Reversible: removing the reference changes only the reference.
  await page.getByRole("button", { name: "Remove design reference" }).click();
  await expect(page.getByText(/^Marked as a design reference on /)).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Use as design reference" })).toBeVisible();
  await expect(page.getByText("An illustrative concept only")).toBeVisible();
  await axe(page);
  await page.getByRole("button", { name: "Use as design reference" }).click();
  await expect(page.getByText(/^Marked as a design reference on /)).toBeVisible();

  // The overview shows the latest concepts.
  await sections.getByRole("link", { name: "Overview" }).click();
  await expect(page.getByText("0 of 3 free designs left")).toBeVisible();
  await expect(page.getByRole("img", { name: /Illustrative concept\.$/ })).toHaveCount(3);
  await expect(page.getByRole("link", { name: "Generate My Design" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "See all designs" })).toBeVisible();
  await axe(page);
});
