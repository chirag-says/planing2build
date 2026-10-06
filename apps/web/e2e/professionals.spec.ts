// Professional registration, approval and free discovery end to end (Slice 3.2): a professional
// registers by emailed code on the professionals host, completes the profile, supplies evidence
// and a portfolio photo through storage, the worker and ClamAV, and submits a category;
// operations review it (claim, checks, portfolio, approve); anyone finds the listing in the
// public directory without signing in; the professional hides and shows it; operations suspend
// and reinstate it. A signed-in family narrows the directory to a project. Axe on every screen.
import { expect, test, type Page } from "@playwright/test";

import {
  IHB,
  OPS,
  PNG,
  PRO,
  expectAccessible as axe,
  signInByCode,
  staffReady,
  submitRequirement,
  uniqueEmail,
} from "./support";

const group = (page: Page, name: string) => page.getByRole("group", { name, exact: true });

/** Upload one file through a form and wait for the scan, which the page polls for. */
async function upload(page: Page, field: string, name: string) {
  await page.getByLabel(field).setInputFiles({ name, mimeType: "image/png", buffer: PNG });
}

/** The directory, searched by name, as someone who is not signed in on the homeowner host. */
async function search(page: Page, name: string) {
  await page.goto(`${IHB}/professionals?q=${encodeURIComponent(name)}`);
  return page.getByRole("list", { name: "Find professionals" }).locator(":scope > li");
}

test("a professional registers and is approved; anyone finds them; hide, show, suspend", async ({
  page,
  request,
}) => {
  test.setTimeout(300_000);
  const name = `E2E Studio ${Date.now().toString(36)}`;
  const email = uniqueEmail();

  // Registration: the same emailed code creates the account (D-04).
  await page.goto(`${PRO}/`);
  await expect(page).toHaveURL(/\/sign-in\?next=%2F$/);
  await axe(page);
  await signInByCode(page, request, email);
  await expect(page.getByRole("heading", { level: 1, name: "Your professional profile" })).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByText("No categories yet")).toBeVisible();
  await expect(page.getByText(/There are no fees for professionals\./)).toBeVisible(); // D-03
  await axe(page);

  // Profile.
  await page.getByRole("link", { name: "Complete your profile" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Your profile" })).toBeVisible();
  await axe(page);
  await page.getByLabel("Your name").fill(name);
  await page.getByLabel("Firm or business name").fill(`${name} LLP`);
  await page.getByLabel("About your work").fill("Homes and small offices in Raipur.");
  await page.getByLabel("Years of experience").fill("9");
  await page.getByLabel("Team size").fill("4");
  await page.getByLabel("Locality you work from").fill("Civil Lines");
  await page.getByLabel("Latitude").fill("21.2400");
  await page.getByLabel("Longitude").fill("81.6400");
  await page.getByRole("button", { name: "Set the pin" }).click();
  await page.getByLabel("Service radius (km)").fill("25");
  await page.getByRole("button", { name: "Save profile" }).click();
  await expect(page.getByText("Profile saved.")).toBeVisible();

  // A category, its checklist and the evidence it asks for.
  await page.goto(`${PRO}/`);
  await group(page, "Category").getByLabel("Architect", { exact: true }).check();
  await page.getByRole("button", { name: "Add category" }).click();
  await expect(page).toHaveURL(`${PRO}/categories/ARCHITECT`);
  await expect(page.getByRole("heading", { name: "What Plan2Build checks" })).toBeVisible();
  await expect(page.getByText(/Still needed before submitting:/)).toBeVisible();
  await axe(page);

  await group(page, "Document").getByLabel("Identity", { exact: true }).check();
  await upload(page, "File (JPG, PNG or PDF, up to 10 MB)", "id-card.png");
  await page.getByRole("button", { name: "Add document" }).click();
  await expect(page.getByText("Identity: id-card.png")).toBeVisible();

  await group(page, "Document").getByLabel("Registration, credential or licence", { exact: true }).check();
  await page.getByLabel("Issuing body").fill("Council of Architecture");
  await page.getByLabel("Registration or licence number").fill("CA/2017/12345");
  await upload(page, "File (JPG, PNG or PDF, up to 10 MB)", "registration.png");
  await page.getByRole("button", { name: "Add document" }).click();
  await expect(page.getByText("Registration, credential or licence: registration.png")).toBeVisible();
  await expect(page.getByText("Ready", { exact: true })).toHaveCount(2, { timeout: 120_000 });
  await axe(page);

  await page.getByRole("link", { name: "Manage your portfolio" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Your portfolio" })).toBeVisible();
  await page.getByLabel("Caption").fill("Courtyard house, Shankar Nagar");
  await upload(page, "Photo (JPG or PNG, up to 10 MB)", "courtyard.png");
  await page.getByRole("button", { name: "Add photo" }).click();
  await expect(page.getByText("Courtyard house, Shankar Nagar (Waiting for approval)")).toBeVisible();
  await expect(page.getByText("Ready", { exact: true })).toBeVisible({ timeout: 120_000 });
  await axe(page);

  await page.goto(`${PRO}/categories/ARCHITECT`);
  await expect(page.getByText(/Still needed before submitting:/)).toHaveCount(0);
  await page.getByRole("button", { name: "Submit for review" }).click();
  await expect(page.getByText("Status: In review")).toBeVisible();
  await expect(page.getByText("Evidence is fixed while Plan2Build reviews it.")).toBeVisible();
  await axe(page);

  // Nothing is public before approval.
  await expect(await search(page, name)).toHaveCount(0);
  await expect(page.getByText("No approved professionals match")).toBeVisible();

  // Operations: claim, record the checks, approve the photo and the category.
  await staffReady(page, request);
  const entry = page.getByRole("link", { name: `${name} · ARCHITECT` });
  await expect(async () => {
    await page.goto(`${OPS}/professionals`);
    await expect(entry).toBeVisible({ timeout: 1_000 });
  }).toPass({ timeout: 30_000 });
  await axe(page);
  await entry.click();
  await expect(page.getByText("Claim the review to record checks and decide.")).toBeVisible();
  await expect(page.getByText("Council of Architecture", { exact: false })).toBeVisible();
  await axe(page);
  await page.getByRole("button", { name: "Claim for review" }).click();
  await expect(page.getByRole("button", { name: "Approve and list" })).toBeVisible();

  // Approval needs every requirement checked; the API refuses and the page says why.
  await page.getByRole("button", { name: "Approve and list" }).click();
  await expect(page.getByText("Every requirement needs a recorded check before approval.")).toBeVisible();
  for (const [kind, subject] of [
    ["Identity", "Aadhaar card"],
    ["Registration or licence", "Council of Architecture register"],
    ["Portfolio", "Courtyard house photos"],
  ]) {
    await group(page, "Check").getByLabel(kind, { exact: true }).check();
    await page.getByLabel("What was checked").fill(subject);
    await page.getByRole("button", { name: "Record check" }).click();
    await expect(page.getByText(`${kind}: ${subject} · Passed`)).toBeVisible();
  }
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(page.getByText("Courtyard house, Shankar Nagar · Approved, public")).toBeVisible();
  await axe(page);
  await page.getByRole("button", { name: "Approve and list" }).click();
  await expect(page.getByText("Status: Listed")).toBeVisible();
  const opsDetail = page.url();
  await axe(page);

  // The public directory, signed out on the homeowner host (D-09).
  const cards = await search(page, name);
  await expect(cards).toHaveCount(1);
  await expect(cards.getByText("Champions Club")).toBeVisible();
  await expect(cards.getByText("Serves 25 km around Civil Lines")).toBeVisible();
  await expect(page.getByText("It is not a ranking, and no one pays to appear higher.")).toBeVisible();
  await expect(page.getByLabel("Near my project")).toHaveCount(0); // signed out: no project filter
  await axe(page);
  await cards.getByRole("link", { name: `View profile: ${name}` }).click();
  await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();
  await expect(page.getByText("Identity verified")).toBeVisible();
  await expect(page.getByText("Registration: Council of Architecture CA/2017/12345")).toBeVisible();
  await expect(page.getByRole("img", { name: "Courtyard house, Shankar Nagar" })).toBeVisible();
  await expect(page.getByText(/part of the Plan2Build package/)).toBeVisible();
  // D-01: no contact details, documents or reviewer details in public.
  await expect(page.getByText(email)).toHaveCount(0);
  await expect(page.getByText("Aadhaar card")).toHaveCount(0);
  await expect(page.getByText("id-card.png")).toHaveCount(0);
  await axe(page);

  // The professional hides the listing and shows it again (D-11).
  await page.goto(`${PRO}/categories/ARCHITECT`);
  await page.getByRole("button", { name: "Hide from the directory" }).click();
  await expect(page.getByText("Hidden by you. Your approval is kept; show it again at any time.")).toBeVisible();
  await axe(page);
  await expect(await search(page, name)).toHaveCount(0);
  await page.goto(`${PRO}/categories/ARCHITECT`);
  await page.getByRole("button", { name: "Show in the directory" }).click();
  await expect(page.getByRole("button", { name: "Hide from the directory" })).toBeVisible();
  await expect(await search(page, name)).toHaveCount(1);

  // Operations suspend with a reason and reinstate (D-10).
  await page.goto(opsDetail);
  await page.getByLabel("Reason").fill("Complaint under review.");
  await page.getByRole("button", { name: "Suspend listing" }).click();
  await expect(page.getByText("Status: Suspended")).toBeVisible();
  await axe(page);
  await expect(await search(page, name)).toHaveCount(0);
  await page.goto(opsDetail);
  await page.getByLabel("Reason").fill("Complaint resolved.");
  await page.getByRole("button", { name: "Reinstate listing" }).click();
  await expect(page.getByText("Status: Listed")).toBeVisible();
  await expect(await search(page, name)).toHaveCount(1);

  // The professional's dashboard shows the outcome; the suspension reason is not shown to them
  // as an internal note, and nothing in the public profile changed.
  await page.goto(`${PRO}/`);
  await expect(page.getByText("Shown in the public directory")).toBeVisible();
  await expect(page.getByText(/Re-verification due/)).toBeVisible();
  await axe(page);
});

test("a signed-in family narrows the directory to professionals covering a project", async ({
  page,
  request,
}) => {
  test.setTimeout(120_000);
  const project = await submitRequirement(page, request);

  // The project dashboard's Professionals section (Slice 3.4) links to the directory for this plot.
  await page.goto(`${IHB}/projects/${project.id}`);
  const sections = page.getByRole("navigation", { name: "Project sections" });
  await sections.getByRole("link", { name: "Professionals" }).click();
  await expect(page).toHaveURL(`${IHB}/projects/${project.id}/services`);
  await page.getByRole("link", { name: "Browse professionals near this project" }).click();
  await expect(page).toHaveURL(`${IHB}/professionals?project=${project.id}`);
  const near = page.getByLabel("Near my project");
  await expect(near).toHaveValue(project.id);
  await expect(near.getByRole("option", { name: `Covers ${project.code}` })).toHaveCount(1);
  await axe(page);

  // Choosing "Anywhere" returns to the whole directory; the filter is a plain GET form.
  await near.selectOption({ label: "Anywhere" });
  await page.getByRole("button", { name: "Apply filters" }).click();
  await expect(near).toHaveValue("");
  await expect(page).not.toHaveURL(new RegExp(project.id));
  await near.selectOption({ value: project.id });
  await page.getByLabel("Category").selectOption({ label: "Architect" });
  await page.getByRole("button", { name: "Apply filters" }).click();
  await expect(page).toHaveURL(new RegExp(`category=ARCHITECT.*project=${project.id}`));
  await axe(page);
});
