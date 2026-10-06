// Slice 1 end to end (Handover 1, public): entry questions, both capture paths, the demo estimate,
// and a homeowner who signs up, creates a project, answers the locked question set, uploads a
// photo that passes the real checks (SeaweedFS + worker + ClamAV), submits, and sees "Submitted".
// Needs the local stack (pnpm local:up, with the demo rate card) and `pnpm dev:web`.
import { expect, test, type Page } from "@playwright/test";

import { IHB, PNG, codeFor, expectAccessible as axe, uniqueEmail } from "./support";

const group = (page: Page, name: string) => page.getByRole("group", { name, exact: true });

async function choose(page: Page, question: string, answer: string) {
  await group(page, question).getByLabel(answer, { exact: true }).check();
}


test("a family not building a new home can leave the type of work and an email", async ({ page }) => {
  await page.goto(`${IHB}/start`);
  await choose(page, "Are you building a new home?", "No");
  await page.getByRole("link", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/need-help$/);
  await choose(page, "Type of work", "Interiors");
  await page.getByLabel("Email address").fill(uniqueEmail());
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByRole("main").getByRole("status")).toHaveText("Thank you. We have your email.");
  await axe(page);
});

test("a family outside Raipur can leave an email", async ({ page }) => {
  await page.goto(`${IHB}/start`);
  await choose(page, "Are you building a new home?", "Yes");
  await choose(page, "Is your plot in Raipur?", "No");
  await page.getByRole("link", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/other-city$/);
  await expect(page.getByText("We're starting in Raipur. Leave your email")).toBeVisible();
  await page.getByLabel("Email address").fill(uniqueEmail());
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByRole("main").getByRole("status")).toHaveText("Thank you. We have your email.");
  await axe(page);
});

test("the estimate is labelled as demonstration figures", async ({ page }) => {
  await page.goto(`${IHB}/`);
  await page.getByRole("link", { name: "See what your house should cost" }).click();
  await page.getByLabel("Total built-up area across all floors (sq ft)").fill("2000");
  await page.getByRole("button", { name: "Estimate" }).click();
  await expect(page.getByText("Demonstration figures, not Plan2Build pricing")).toBeVisible();
  await expect(page.getByText("Demo data")).toBeVisible();
  await expect(page.getByRole("cell", { name: "Foundation and footings" })).toBeVisible();
  await axe(page);
});

test("a homeowner signs up, answers the requirement, uploads a photo and submits", async ({
  page,
  request,
}) => {
  test.setTimeout(240_000);
  const email = uniqueEmail();

  // Entry, then sign-up by emailed code, returning to the project start.
  await page.goto(`${IHB}/`);
  await page.getByRole("link", { name: "Start your build plan" }).click();
  await choose(page, "Are you building a new home?", "Yes");
  await choose(page, "Is your plot in Raipur?", "Yes");
  await axe(page);
  await page.getByRole("link", { name: "Start my requirement" }).click();
  await expect(page).toHaveURL(/\/sign-in\?next=%2Fprojects%2Fnew$/);
  await page.getByLabel("Email address").fill(email);
  await page.getByRole("button", { name: "Email me a code" }).click();
  await page.getByLabel("6-digit code").fill(await codeFor(request, email));
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/projects\/new$/);
  await page.getByRole("button", { name: "Create my project" }).click();
  // Generous: in development the first visit compiles the route.
  await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+\/requirement$/, { timeout: 30_000 });

  // Step 1: the plot.
  await expect(page.getByRole("heading", { name: "Your plot" })).toBeVisible();
  await axe(page);
  await page.getByLabel("Latitude").fill("21.2514");
  await page.getByLabel("Longitude").fill("81.6296");
  await page.getByRole("button", { name: "Set the pin" }).click();
  await expect(page.getByText("Pin at 21.25140, 81.62960")).toBeVisible();
  await page.getByLabel("Locality", { exact: true }).fill("Shankar Nagar");
  await choose(page, "What are you building?", "Independent house");
  await choose(page, "Is your plot a rectangle?", "Yes");
  await page.getByLabel("Plot width (feet)").fill("40");
  await page.getByLabel("Plot depth (feet)").fill("60");
  await choose(page, "Which way does the plot face?", "East");
  const setbacks = group(page, "Setbacks (open space to leave on each side), in feet");
  await setbacks.getByLabel("Front", { exact: true }).fill("10");
  await setbacks.getByLabel("Back", { exact: true }).fill("5");
  await setbacks.getByLabel("Left: Not sure").check();
  await setbacks.getByLabel("Right", { exact: true }).fill("3.5");
  await page.getByRole("button", { name: "Save and continue" }).click();

  // Step 2: the house. Style and quality tier are separate questions (R-11).
  await expect(page.getByRole("heading", { name: "Your house" })).toBeVisible();
  await page.getByRole("spinbutton", { name: "Total built-up area across all floors (sq ft)" }).fill("2650");
  await choose(page, "How many floors?", "Ground + 1");
  await choose(page, "Will the house have a basement?", "No");
  await choose(page, "Construction quality tier", "Premium");
  await choose(page, "Style of the house (optional)", "Modern");
  await choose(page, "Bedrooms", "3");
  await choose(page, "Bathrooms", "3");
  await choose(page, "Pooja room", "Yes");
  await choose(page, "Car parking", "Yes");
  await choose(page, "Vastu", "Where possible");
  await page.getByRole("button", { name: "Save and continue" }).click();

  // Step 3: budget and timing.
  await expect(page.getByRole("heading", { name: "Budget and timing" })).toBeVisible();
  await choose(page, "Your construction budget (excluding land)", "₹60L to ₹80L");
  await choose(page, "When do you plan to start building?", "3 to 6 months");
  await choose(page, "Has construction started?", "No");
  await choose(page, "Does your family already have a contractor you want to use?", "No");
  await choose(page, "Do you already have a quote from any contractor?", "No");
  await page.getByRole("button", { name: "Save and continue" }).click();

  // Step 4: the family's own ranking (R-12).
  await expect(page.getByRole("heading", { name: "What matters most" })).toBeVisible();
  for (const item of ["Quality of work", "Finishing on time", "Staying within budget", "Experience with similar homes"]) {
    await page.getByRole("button", { name: `Add ${item}` }).click();
  }
  await page.getByRole("button", { name: "Move Finishing on time up" }).click();
  await page.getByRole("button", { name: "Save and continue" }).click();

  // Step 5: notes and a photo that goes through storage, the worker and ClamAV.
  await expect(page.getByRole("heading", { name: "Anything else" })).toBeVisible();
  await page.getByLabel("Anything else we should know?").fill("Corner plot.");
  await page.locator('input[type="file"]').setInputFiles({
    name: "site.png",
    mimeType: "image/png",
    buffer: PNG,
  });
  await expect(page.getByText("site.png")).toBeVisible();
  await expect(page.getByText("Ready", { exact: true })).toBeVisible({ timeout: 120_000 });
  await page.getByRole("button", { name: "Save and continue" }).click();

  // Review and submit.
  await expect(page.getByRole("heading", { name: "Check and submit" })).toBeVisible();
  await expect(page.getByText("1. Finishing on time; 2. Quality of work")).toBeVisible();
  await expect(page.getByText("Front: 10, Back: 5, Left: Not sure, Right: 3.5")).toBeVisible();
  await axe(page);
  await page.getByRole("button", { name: "Submit my requirement" }).click();
  const confirm = page.getByRole("alertdialog", { name: "Submit your requirement?" });
  await axe(page);
  await confirm.getByRole("button", { name: "Submit", exact: true }).click();

  await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+$/);
  await expect(page).toHaveTitle(/^Project P2B-RPR-\d+ \| Plan2Build$/);
  await expect(page.getByText("Status: Submitted")).toBeVisible();
  // The free dashboard opens at once; the review runs in the background (PD-21).
  await expect(page.getByText("Your project is being reviewed by Plan2Build.")).toBeVisible();
  const sections = page.getByRole("navigation", { name: "Project sections" });
  for (const name of ["Overview", "Requirement", "Estimate", "Documents"]) {
    await expect(sections.getByRole("link", { name })).toBeVisible();
  }
  await expect(sections.getByRole("link", { name: "Construction stages" })).toHaveCount(0);
  await expect(sections.getByRole("link", { name: "Overview" })).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("heading", { name: "Indicative estimate" })).toBeVisible();
  await expect(page.getByText(/not a quote/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Plan2Build package" })).toBeVisible();
  await expect(page.getByText("You use only the services you need.", { exact: false })).toBeVisible();
  await expect(page.getByText("Available once Plan2Build has reviewed your project.")).toBeVisible();
  await axe(page);

  await sections.getByRole("link", { name: "Estimate" }).click();
  await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+\/estimate$/);
  await expect(page).toHaveTitle(/^Estimate · Project P2B-RPR-\d+ \| Plan2Build$/);
  await expect(page.getByText("Demo data")).toBeVisible();
  await expect(page.getByText(/Based on 2,650 sq ft, Ground \+ 1, Premium quality, in Raipur\./)).toBeVisible();
  await axe(page);

  await sections.getByRole("link", { name: "Requirement" }).click();
  await expect(page.getByRole("heading", { name: "Your requirement" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Update your requirement" })).toHaveCount(0);
  await axe(page);

  await sections.getByRole("link", { name: "Documents" }).click();
  await expect(page.getByRole("button", { name: "Download: site.png" })).toBeVisible();
  await axe(page);

  await page.getByRole("navigation", { name: "Breadcrumb" }).getByRole("link", { name: "My projects" }).click();
  await expect(page).toHaveURL(`${IHB}/projects`);
  await expect(page.getByRole("heading", { level: 1, name: "My projects" })).toBeVisible();
  await expect(page).toHaveTitle("My projects | Plan2Build");
  await expect(page.getByText("Status: Submitted")).toBeVisible();
  await axe(page);
});
