// LOCAL SEED, NOT COMMITTED: builds an advanced homeowner project for overview screenshots and
// saves the family's browser state to /tmp/ihb-rich.json (project id in /tmp/ihb-rich.json.project).
import { writeFileSync } from "node:fs";

import { expect, test } from "@playwright/test";

import type { APIRequestContext, Browser, Page } from "@playwright/test";

import { IHB, PNG, PRO, api, projectWithPackage, signInByCode, sql, uniqueEmail } from "./support";

/** support.ts contractor() + engagedContractor(), waiting on the URL (the pro dashboard is being redesigned). */
async function engaged(page: Page, request: APIRequestContext, browser: Browser, projectId: string, name: string) {
  const pro = await (await browser.newContext()).newPage();
  const email = uniqueEmail();
  await pro.goto(`${PRO}/sign-in`);
  await signInByCode(pro, request, email);
  await expect(pro).toHaveURL(`${PRO}/`, { timeout: 30_000 });
  const profileId = sql(`
    UPDATE professional_profiles SET display_name = '${name}', firm_name = '${name}',
      base_locality = 'Civil Lines', base_geom = ST_GeogFromText('SRID=4326;POINT(81.64 21.24)'),
      service_radius_km = 25
    WHERE user_id = (SELECT user_id FROM user_contacts WHERE normalized = '${email}')
    RETURNING id;`).split("\n")[0];
  sql(`INSERT INTO professional_categories (id, profile_id, category_code, listing_state, listed_at)
       VALUES (gen_random_uuid(), '${profileId}', 'CONTRACTOR', 'LISTED', now());`);
  const sent = await api(page, IHB, "POST", `/api/v1/projects/${projectId}/connections`, {
    category: "CONTRACTOR", profile_id: profileId, contact_name: "Asha Verma", contact_phone: "+91 98765 43210",
  });
  const row = (sent.categories as { code: string; connections: { id: string; profile_id: string }[] }[]).find(
    (c) => c.code === "CONTRACTOR",
  )!;
  const connectionId = row.connections.find((c) => c.profile_id === profileId)!.id;
  await api(pro, PRO, "POST", `/api/v1/pro/connections/${connectionId}/accept`, { phone: "+91 90000 11111" });
  const engagementId = sql(`SELECT id FROM project_engagements WHERE project_id = '${projectId}'
    AND category_code = 'CONTRACTOR' AND state = 'ACTIVE'`);
  return { pro, engagementId };
}

test("seed an advanced homeowner project", async ({ page, request, browser }) => {
  test.setTimeout(600_000);
  const suffix = Date.now().toString(36).slice(-4).toUpperCase();
  const project = await projectWithPackage(page, request);
  const { pro, engagementId } = await engaged(page, request, browser, project.id, `Sahu Constructions ${suffix}`);

  // The family's own architect.
  await api(page, IHB, "POST", `/api/v1/projects/${project.id}/engagements`, {
    category: "ARCHITECT",
    name: "Kavya Rao",
    firm: "Studio Arka",
    contact: "+91 98260 44321",
  });

  // Stage 1 under way, then a completion request: the family has a stage to confirm.
  await pro.goto(`${PRO}/engagements/${engagementId}`);
  await pro.getByRole("link", { name: "Construction execution" }).click();
  const form = pro.getByTestId("update-form");
  await form.getByLabel("Note").fill("Site cleared and marked out.");
  await form.getByLabel(/^Photos/).setInputFiles({ name: "site.png", mimeType: "image/png", buffer: PNG });
  await form.getByRole("button", { name: "Post update" }).click();
  await expect(pro.getByText("Update posted.")).toBeVisible({ timeout: 60_000 });
  await form.getByLabel("Update type").selectOption("COMPLETION_REQUEST");
  await form.getByLabel("Note").fill("Stage complete, please confirm.");
  await form.getByLabel(/^Photos/).setInputFiles({ name: "done.png", mimeType: "image/png", buffer: PNG });
  await form.getByRole("button", { name: "Post update" }).click();
  await expect(pro.getByTestId("pro-stage-1-x").getByTestId("stage-state")).toHaveText("Completion requested", {
    timeout: 60_000,
  });

  // One concept design, for the house visual.
  await page.goto(`${IHB}/projects/${project.id}/designs`);
  await page.getByRole("button", { name: "Generate My Design" }).click();
  await expect(page.getByRole("list", { name: "Designs" }).getByRole("img").first()).toBeVisible({ timeout: 90_000 });

  await page.context().storageState({ path: "/tmp/ihb-rich.json" });
  writeFileSync("/tmp/ihb-rich.json.project", project.id);
});
