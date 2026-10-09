// Shared helpers for the end-to-end suite. Every spec runs on a phone and a desktop project
// (playwright.config.ts); the helpers hide the one difference between them, where the homeowner
// header keeps the account (a slide-out menu below 640 px, an Account dropdown above).
import { execFileSync } from "node:child_process";
import { createHmac, randomUUID } from "node:crypto";
import path from "node:path";

import AxeBuilder from "@axe-core/playwright";
import { expect, type APIRequestContext, type Browser, type Locator, type Page } from "@playwright/test";

export const IHB = process.env.E2E_IHB_ORIGIN ?? "http://ihb.localhost:8080";
export const PRO = process.env.E2E_PRO_ORIGIN ?? "http://pro.localhost:8080";
export const MAILPIT = process.env.E2E_MAILPIT_URL ?? "http://localhost:8025";

// A real 1x1 PNG, so the content checks have something genuine to decode.
export const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64",
);

export const uniqueEmail = () =>
  `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.in`;

/** The newest code sent to `email`. `earlier` is how many emails it had before this sign-in. */
export async function codeFor(
  request: APIRequestContext,
  email: string,
  earlier = 0,
): Promise<string> {
  for (let attempt = 0; attempt < 30; attempt++) {
    const search = await request.get(`${MAILPIT}/api/v1/search`, {
      params: { query: `to:"${email}"` },
    });
    const { messages } = (await search.json()) as { messages: { ID: string }[] };
    if (messages.length > earlier) {
      const message = await (await request.get(`${MAILPIT}/api/v1/message/${messages[0].ID}`)).json();
      const match = /\b(\d{6})\b/.exec(message.Text as string);
      if (match) return match[1];
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`no code arrived for ${email}`);
}

/** WCAG 2.0 A/AA and 2.2 AA on whatever the page shows now (UI_DESIGN_SYSTEM.md section 12). */
export async function expectAccessible(page: Page) {
  // Colours are measured once running transitions end (a button leaving its busy state fades).
  // Endless loops (the public website's ticker and crane, UI_DESIGN_SYSTEM.md 11) never finish
  // and change no colour, so only finite animations are waited for.
  await page.evaluate(() =>
    Promise.all(
      document
        .getAnimations()
        .filter((animation) => animation.effect?.getComputedTiming().iterations !== Infinity)
        .map((animation) => animation.finished.catch(() => null)),
    ),
  );
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}

export function isPhone(page: Page): boolean {
  return (page.viewportSize()?.width ?? 0) < 640;
}

/** Wait for an element's open animations (dialogs fade and zoom in) before measuring colours. */
export async function animationsDone(element: Locator): Promise<void> {
  await element.evaluate((node) =>
    Promise.all(node.getAnimations({ subtree: true }).map((animation) => animation.finished)),
  );
}

async function phoneMenu(page: Page): Promise<Locator> {
  const menu = page.getByRole("dialog", { name: "Menu" });
  // A click that lands before hydration does nothing; retry until the menu is open.
  await expect(async () => {
    await page.getByRole("button", { name: "Open menu" }).click();
    await expect(menu).toBeVisible({ timeout: 1_000 });
  }).toPass({ timeout: 15_000 });
  // Let the slide-in finish: mid-animation the sheet is partly transparent and axe would
  // measure blended colours.
  await animationsDone(menu);
  return menu;
}

/** The "Sign in" link in the header, opening the phone menu first when needed. */
export async function signInLink(page: Page): Promise<Locator> {
  const area = isPhone(page)
    ? await phoneMenu(page)
    : page.getByRole("navigation", { name: "Main" });
  return area.getByRole("link", { name: "Sign in" });
}

/** The header's sign-out control, opened and checked for accessibility while it is open. */
export async function openSignOut(page: Page): Promise<Locator> {
  if (isPhone(page)) {
    const menu = await phoneMenu(page);
    const button = menu.getByRole("button", { name: "Sign out" });
    await expect(button).toBeVisible();
    await expectAccessible(page);
    return button;
  }
  const item = page.getByRole("menuitem", { name: "Sign out" });
  await expect(async () => {
    await page.getByRole("button", { name: "Account" }).click();
    await expect(item).toBeVisible({ timeout: 1_000 });
  }).toPass({ timeout: 15_000 });
  await expectAccessible(page);
  return item;
}

export const OPS = process.env.E2E_OPS_ORIGIN ?? "http://admin.localhost:8080";
const COMPOSE = process.env.E2E_COMPOSE_FILE ?? path.resolve(process.cwd(), "../../infra/local/compose.yml");

/** A staff account made the way operations make one: the server-side command (no web path). */
export function grantStaff(email: string, role: "OPS" | "ADMIN"): void {
  execFileSync(
    "docker",
    ["compose", "-f", COMPOSE, "exec", "-T", "api", "python", "-m", "p2b.identity.staff", "grant",
      "--email", email, "--role", role, "--reason", "end-to-end test"],
    { stdio: "pipe" },
  );
}

function base32(secret: string): Buffer {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = 0;
  let value = 0;
  const bytes: number[] = [];
  for (const char of secret.replace(/[\s=]/g, "").toUpperCase()) {
    value = ((value << 5) | alphabet.indexOf(char)) & 0xfff;
    bits += 5;
    if (bits >= 8) {
      bytes.push((value >>> (bits - 8)) & 0xff);
      bits -= 8;
    }
  }
  return Buffer.from(bytes);
}

/** RFC 6238 TOTP (SHA-1, 30 s, 6 digits), as an authenticator app computes it. */
export function totp(secret: string, offsetSteps = 0): string {
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30_000) + offsetSteps));
  const digest = createHmac("sha1", base32(secret)).update(counter).digest();
  const offset = digest[digest.length - 1] & 0x0f;
  return String((digest.readUInt32BE(offset) & 0x7fffffff) % 1_000_000).padStart(6, "0");
}

/** An OPS staff member, signed in on the admin host with TOTP set up. Returns the TOTP secret. */
export async function staffReady(
  page: Page,
  request: APIRequestContext,
  checkScreens = false,
  role: "OPS" | "ADMIN" = "OPS",
) {
  const email = `e2e-ops-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@example.in`;
  grantStaff(email, role);
  await page.goto(`${OPS}/`);
  await expect(page).toHaveURL(/\/sign-in\?next=%2Fqueue$/);
  if (checkScreens) await expectAccessible(page);
  await signInByCode(page, request, email);
  await expect(page).toHaveURL(`${OPS}/mfa/setup`, { timeout: 30_000 });
  if (checkScreens) await expectAccessible(page);
  await page.getByRole("button", { name: "Show my setup code" }).click();
  const secret = (await page.getByTestId("mfa-secret").textContent()) ?? "";
  await expect(page.getByRole("img", { name: "QR code for your authenticator app" })).toBeVisible();
  if (checkScreens) await expectAccessible(page);
  await page.getByLabel("6-digit code from your app").fill(totp(secret));
  await page.getByRole("button", { name: "Confirm" }).click();
  // Ten recovery codes are hashed with argon2id on confirm: deliberately slow, more so in parallel.
  await expect(page.getByRole("list", { name: "Save your recovery codes" }).getByRole("listitem")).toHaveCount(10, {
    timeout: 20_000,
  });
  if (checkScreens) await expectAccessible(page);
  await page.getByLabel("I have saved these codes somewhere safe").check();
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(`${OPS}/queue`);
  return { email, secret };
}

/** Accept the claimed submission: every eligibility check passed (F-05), then Accept. */
export async function acceptWithChecklist(page: Page, check?: () => Promise<void>) {
  await page.getByRole("button", { name: "Accept" }).click();
  const dialog = page.getByRole("dialog", { name: "Accept this submission?" });
  await expect(dialog.getByText("Every check must pass to accept.")).toBeVisible();
  for (const passed of await dialog.getByLabel("Passed", { exact: true }).all()) {
    await passed.check();
  }
  if (check) {
    await animationsDone(dialog);
    await check();
  }
  await dialog.getByRole("button", { name: "Accept", exact: true }).click();
  await expect(page.getByText("Status: Accepted")).toBeVisible();
}

/** Sign in on a host by emailed code, through the page. */
export async function signInByCode(
  page: Page,
  request: APIRequestContext,
  email: string,
  earlier = 0,
) {
  await page.getByLabel("Email address").fill(email);
  await page.getByRole("button", { name: "Email me a code" }).click();
  await page.getByLabel("6-digit code").fill(await codeFor(request, email, earlier));
  await page.getByRole("button", { name: "Sign in" }).click();
}

export const ANSWERS = {
  location: { lat: 21.2514, lng: 81.6296 },
  locality: "Shankar Nagar",
  property_type: "OTHER",
  property_type_other: "A small hostel",
  plot_is_rectangular: true,
  plot_width_ft: 40,
  plot_depth_ft: 60,
  facing: "E",
  setbacks: { FRONT: 10, BACK: 5, LEFT: "NOT_SURE", RIGHT: 3 },
  built_up_area_sqft: 2650,
  floors: "G_PLUS_1",
  basement: true,
  quality_tier: "PREMIUM",
  bedrooms: "3",
  bathrooms: "3",
  pooja_room: true,
  car_parking: true,
  vastu: "WHERE_POSSIBLE",
  budget_band: "60L_80L",
  start_timeline: "3_6M",
  construction_started: false,
  has_contractor: false,
  has_quote: false,
  priorities: ["QUALITY", "ON_TIME", "WITHIN_BUDGET", "SIMILAR_HOMES"],
};

export interface Submitted {
  id: string;
  code: string;
}

/** A homeowner signs up and submits through the API, from inside the page (same origin). */
export async function submitRequirement(page: Page, request: APIRequestContext): Promise<Submitted> {
  const email = uniqueEmail();
  await page.goto(`${IHB}/sign-in`);
  const call = (path: string, method: string, body?: unknown, key?: string) =>
    page.evaluate(
      async ({ path, method, body, key }) => {
        const headers: Record<string, string> = {
          "Content-Type": "application/json",
          "X-Requested-With": "plan2build",
        };
        if (key) headers["Idempotency-Key"] = key;
        const response = await fetch(path, { method, headers, body: JSON.stringify(body) });
        return { status: response.status, body: await response.json() };
      },
      { path, method, body, key },
    );
  const started = await call("/api/v1/auth/otp/start", "POST", { email });
  const code = await codeFor(request, email);
  await call("/api/v1/auth/otp/verify", "POST", { challenge_id: started.body.challenge_id, code });
  const created = await call("/api/v1/projects", "POST", { city: "Raipur" }, crypto.randomUUID());
  const id = created.body.project.project_id as string;
  await call(`/api/v1/projects/${id}/requirement`, "PUT", { answers: ANSWERS, version: 1 });
  const submitted = await call(
    `/api/v1/projects/${id}/requirement/submit`, "POST", { version: 2 }, crypto.randomUUID(),
  );
  expect(submitted.status).toBe(200);
  return { id, code: submitted.body.project.code as string };
}

/** Pause or resume the local worker container, to hold a queued job where a test needs it. */
export function workerContainer(action: "pause" | "unpause"): void {
  execFileSync("docker", ["compose", "-f", COMPOSE, action, "worker"], { stdio: "pipe" });
}

/** SQL against the local dev database, for seeding states the UI cannot reach on its own. */
export function sql(query: string): string {
  return execFileSync(
    "docker",
    ["compose", "-f", COMPOSE, "exec", "-T", "db", "sh", "-c", 'psql -qAt -U "$POSTGRES_USER" -d p2b'],
    { input: query, stdio: ["pipe", "pipe", "pipe"] },
  ).toString().trim();
}

// --- shared by the 3.6 and 3.7 specs ---------------------------------------------------------

export async function openFromQueue(page: Page, code: string) {
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

export async function projectWithPackage(page: Page, request: APIRequestContext): Promise<Submitted> {
  const project = await submitRequirement(page, request);
  await staffReady(page, request);
  await openFromQueue(page, project.code);
  await page.getByRole("button", { name: "Claim for review" }).click();
  await acceptWithChecklist(page);
  await page.goto(`${IHB}/projects/${project.id}/package`);
  await page.getByText("In full now").click();
  await page.getByLabel("Name on the invoice").fill("Asha Verma");
  await page.getByLabel("Billing address").fill("12 Civil Lines, Raipur");
  await page.getByLabel("State").selectOption({ label: "Chhattisgarh" });
  await page.getByLabel(/I accept the purchase and refund terms/).check();
  await page.getByRole("button", { name: "Continue to payment" }).click();
  await expect(page).toHaveURL(/\/package\/orders\/[0-9a-f-]+$/);
  await page.getByRole("button", { name: /^Pay ₹/ }).click();
  const checkout = page.getByRole("dialog", { name: "Test payment" });
  await animationsDone(checkout);
  await checkout.getByRole("button", { name: "Pay (test)" }).click();
  await expect(page.getByText("Status: Paid")).toBeVisible({ timeout: 45_000 });
  return project;
}

/** A JSON call from inside the page (same origin, the page's cookies, the web client's CSRF
 * headers): the browser resolves the *.localhost hosts, the test runner does not. */
export async function api(page: Page, origin: string, method: string, path: string, data?: unknown) {
  if (!page.url().startsWith(origin)) await page.goto(`${origin}/`);
  const result = await page.evaluate(
    async ({ method, path, data, key }) => {
      const response = await fetch(path, {
        method,
        headers: { "X-Requested-With": "plan2build", "Content-Type": "application/json", "Idempotency-Key": key },
        body: data === undefined ? undefined : JSON.stringify(data),
      });
      return { ok: response.ok, text: await response.text() };
    },
    { method, path, data, key: randomUUID() },
  );
  expect(result.ok, `${method} ${path}: ${result.text}`).toBeTruthy();
  return JSON.parse(result.text) as Record<string, never>;
}

/** A listed contractor near the plot, signed in on its own browser context. */
export async function contractor(browser: Browser, request: APIRequestContext, name: string): Promise<Page> {
  const page = await (await browser.newContext()).newPage();
  const email = uniqueEmail();
  await page.goto(`${PRO}/sign-in`);
  await signInByCode(page, request, email);
  await expect(page.getByLabel("Your professional identity")).toBeVisible({ timeout: 30_000 });
  const profileId = sql(`
    UPDATE professional_profiles SET display_name = '${name}', firm_name = '${name} LLP',
      base_locality = 'Civil Lines', base_geom = ST_GeogFromText('SRID=4326;POINT(81.64 21.24)'),
      service_radius_km = 25
    WHERE user_id = (SELECT user_id FROM user_contacts WHERE normalized = '${email}')
    RETURNING id;`).split("\n")[0];
  sql(`INSERT INTO professional_categories (id, profile_id, category_code, listing_state, listed_at)
       VALUES (gen_random_uuid(), '${profileId}', 'CONTRACTOR', 'LISTED', now());`);
  return page;
}

export async function confirmationCode(request: APIRequestContext, email: string, earlier: number): Promise<string> {
  for (let attempt = 0; attempt < 60; attempt++) {
    const search = await request.get(`${MAILPIT}/api/v1/search`, {
      params: { query: `to:"${email}" subject:"confirmation code"` },
    });
    const { messages } = (await search.json()) as { messages: { ID: string }[] };
    if (messages.length > earlier) {
      const message = await (await request.get(`${MAILPIT}/api/v1/message/${messages[0].ID}`)).json();
      const match = /\b(\d{6})\b/.exec(message.Text as string);
      if (match) return match[1];
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`no confirmation code arrived for ${email}`);
}

export async function codeCount(request: APIRequestContext, email: string): Promise<number> {
  const search = await request.get(`${MAILPIT}/api/v1/search`, {
    params: { query: `to:"${email}" subject:"confirmation code"` },
  });
  return ((await search.json()) as { messages: unknown[] }).messages.length;
}

/** A listed contractor engaged on the project: the family's connection request, accepted through
 * the API (the 3.4 spec covers those screens). Returns the contractor's page and engagement id. */
export async function engagedContractor(
  page: Page, request: APIRequestContext, browser: Browser, projectId: string, name: string,
): Promise<{ pro: Page; engagementId: string; userId: string }> {
  const pro = await contractor(browser, request, name);
  const profileId = sql(`SELECT id FROM professional_profiles WHERE display_name = '${name}'`);
  const sent = await api(page, IHB, "POST", `/api/v1/projects/${projectId}/connections`, {
    category: "CONTRACTOR", profile_id: profileId, contact_name: "Asha Verma", contact_phone: "+91 98765 43210",
  });
  const row = (sent.categories as { code: string; connections: { id: string; profile_id: string }[] }[])
    .find((c) => c.code === "CONTRACTOR")!;
  const connectionId = row.connections.find((c) => c.profile_id === profileId)!.id;
  await api(pro, PRO, "POST", `/api/v1/pro/connections/${connectionId}/accept`, { phone: "+91 90000 11111" });
  const engagementId = sql(`SELECT id FROM project_engagements WHERE project_id = '${projectId}'
    AND category_code = 'CONTRACTOR' AND state = 'ACTIVE'`);
  const userId = sql(`SELECT user_id FROM professional_profiles WHERE id = '${profileId}'`);
  return { pro, engagementId, userId };
}

/** The sidebar group each project section sits in (homeowner overview v3: seven groups). */
const SECTION_GROUP: Record<string, string> = {
  Overview: "Home",
  Requirement: "My project",
  Estimate: "My project",
  Designs: "My project",
  Package: "My project",
  "Build Plan": "My project",
  Professionals: "Quotes",
  "Contractor quotes": "Quotes",
  "Construction stages": "Construction",
  Specification: "Construction",
  "Needs attention": "Home",
  "Meet your team": "Home",
};

/**
 * A project section's link in the "Project sections" navigation. On wide screens only the current
 * group is open, so a section in a closed group is reached through its group first; the phone row
 * lists every section.
 */
export async function openSection(page: Page, name: string): Promise<void> {
  const sections = page.getByRole("navigation", { name: "Project sections" });
  const link = sections.getByRole("link", { name, exact: true });
  if (!(await link.isVisible())) {
    const group = SECTION_GROUP[name];
    if (group) await sections.getByRole("link", { name: group, exact: true }).click();
  }
  // A click that lands before hydration does nothing; retry until the section is open.
  await expect(async () => {
    await link.click();
    await expect(link).toHaveAttribute("aria-current", "page", { timeout: 2_000 });
  }).toPass({ timeout: 20_000 });
}
