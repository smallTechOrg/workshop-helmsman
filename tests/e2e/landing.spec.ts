import { test, expect, type Page } from '@playwright/test';
import {
  APP_BASE,
  CREATE_URL,
  LANDING_URL,
  ORIGIN,
  composePublicWorkshop,
  extractUrl,
} from './helpers';

/**
 * Phase 6 — C5 public marketing landing page (capabilities.md §C5,
 * api.md §`GET /`, architecture.md §Serving the landing page at `/`).
 *
 * `/` is a real 200 HTML page, not a 307 into the app. It carries the hero +
 * single CTA, the feature blocks, the how-it-works walkthrough and the FAQ,
 * and it links to the admin console NOWHERE. "Your workshops" is absent on a
 * fresh browser and appears — with working quick links — only after that same
 * browser has publicly created a workshop (localStorage, not auth).
 */

const uncaughtErrors: string[] = [];

function watch(page: Page): Page {
  page.on('pageerror', (err) => uncaughtErrors.push(String(err)));
  return page;
}

test.describe('Phase 6 — public landing page at /', () => {
  test('GET / returns 200 text/html directly — not a redirect into /app/', async ({ request }) => {
    const res = await request.get(LANDING_URL, { maxRedirects: 0 });
    expect(res.status(), 'GET / must serve the landing page, not 307').toBe(200);
    expect(res.headers()['content-type'] ?? '').toContain('text/html');
    const html = await res.text();
    // The gate greps the served bytes for the CTA; assert the same contract.
    expect(html).toContain('data-testid="landing-cta"');
  });

  test('GET /admin is the pretty redirect to the relocated console', async ({ request }) => {
    const res = await request.get(`${ORIGIN}/admin`, { maxRedirects: 0 });
    expect(res.status()).toBe(307);
    expect(res.headers()['location']).toBe('/app/admin/');
  });

  test('every marketing section renders, styled, with a single primary CTA', async ({ page }) => {
    watch(page);
    const res = await page.goto(LANDING_URL);
    expect(res?.status()).toBe(200);
    expect(new URL(page.url()).pathname, '/ must not redirect').toBe('/');

    await expect(page.getByTestId('landing-hero')).toBeVisible();
    await expect(page.getByTestId('landing-features')).toBeVisible();
    await expect(page.getByTestId('landing-how-it-works')).toBeVisible();
    await expect(page.getByTestId('landing-faq')).toBeVisible();

    // Exactly one primary CTA (C5 §1: "No second competing CTA").
    const cta = page.getByTestId('landing-cta');
    await expect(cta).toHaveCount(1);
    await expect(cta).toBeVisible();
    await expect(cta).toContainText(/create your workshop/i);

    // Styled render, not a bare-HTML fallback (same bar as smoke.spec.ts).
    expect(await page.evaluate(() => document.styleSheets.length)).toBeGreaterThan(0);
    const fontFamily = await page.evaluate(() => getComputedStyle(document.body).fontFamily);
    expect(fontFamily.toLowerCase()).not.toContain('times');

    // Content bar: the FAQ states the honest limits, how-it-works is a walkthrough.
    await expect(page.getByTestId('landing-faq')).toContainText(/no account|no login/i);
    await expect(page.getByTestId('landing-how-it-works')).toContainText(/join link/i);
  });

  test('the CTA navigates a keyless browser to the public create flow', async ({ page }) => {
    watch(page);
    await page.goto(LANDING_URL);
    await page.getByTestId('landing-cta').click();
    await expect(page.getByTestId('create-page')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId('composer')).toBeVisible();
    expect(new URL(page.url()).pathname).toBe('/app/create/');
    // Keyless: the create flow never presents the admin key gate.
    await expect(page.getByTestId('admin-key-input')).toHaveCount(0);
  });

  test('the landing page never links to or exposes the admin console', async ({ page }) => {
    watch(page);
    await page.goto(LANDING_URL);
    await expect(page.getByTestId('landing-hero')).toBeVisible();

    const adminHrefs = await page.$$eval('a[href]', (as) =>
      as.map((a) => a.getAttribute('href') ?? '').filter((h) => /(^|\/)admin(\/|$|\?|#)/i.test(h)),
    );
    expect(adminHrefs, 'no anchor on / may point at the admin console').toEqual([]);
    await expect(page.getByTestId('admin-key-input')).toHaveCount(0);
    await expect(page.getByTestId('workshop-card')).toHaveCount(0);
  });

  test('"Your workshops" is absent on a fresh browser and appears after a public creation', async ({
    browser,
  }) => {
    const ctx = await browser.newContext();
    ctx.setDefaultTimeout(15_000);
    ctx.setDefaultNavigationTimeout(30_000);
    const page = watch(await ctx.newPage());

    try {
      // Fresh context, empty localStorage → the section is absent entirely
      // (C5 §4: "no empty state, no teaser").
      await page.goto(LANDING_URL);
      await expect(page.getByTestId('landing-hero')).toBeVisible();
      await expect(page.getByTestId('your-workshops')).toHaveCount(0);

      // Create a workshop publicly IN THIS SAME CONTEXT (no admin key ever).
      const name = `E2E Landing Remembered ${Date.now()}`;
      await page.goto(CREATE_URL);
      await expect(page.getByTestId('create-page')).toBeVisible();
      const { joinUrl } = await composePublicWorkshop(page, {
        name,
        milestones: [{ title: 'Say hello', content: 'Introduce yourself to the room.' }],
        email: `e2e.landing.${Date.now()}@example.com`,
      });

      // Back on the landing page the browser now remembers it.
      await page.goto(LANDING_URL);
      const yours = page.getByTestId('your-workshops');
      await expect(yours).toBeVisible();
      await expect(yours).toContainText(name);
      // Stated plainly: this is a browser convenience, not an account.
      await expect(yours).toContainText(/browser|not an account/i);

      // The quick link actually works — it opens that workshop's dashboard.
      const quick = yours.getByTestId('your-workshop-link').first();
      await expect(quick).toBeVisible();
      const href = (await quick.getAttribute('href')) ?? '';
      const dashboardUrl = href
        ? extractUrl(href.startsWith('http') ? href : `${ORIGIN}${href}`, '/f/')
        : extractUrl(await quick.innerText(), '/f/');
      expect(dashboardUrl).toMatch(/\/f\/[A-Za-z0-9_-]{20,}$/);
      await page.goto(dashboardUrl);
      await expect(page).toHaveURL(new RegExp(`${APP_BASE}/f/\\?t=[A-Za-z0-9_-]+`));
      const dashboard = page.getByTestId('dashboard-page');
      await expect(dashboard).toBeVisible();
      await expect(dashboard).toContainText(name);

      // The join link it stored is the real one for the same workshop.
      expect(joinUrl).toMatch(/\/j\/[A-Za-z0-9_-]{6,}$/);
    } finally {
      await ctx.close();
    }
  });

  test('no uncaught page errors on the landing surfaces', async () => {
    expect(uncaughtErrors, uncaughtErrors.join('\n') || 'clean').toEqual([]);
  });
});
