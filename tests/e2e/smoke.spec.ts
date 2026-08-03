import { test, expect } from '@playwright/test';
import { ADMIN_BASE, ORIGIN } from './helpers';

/**
 * Independent smoke checks against the live single-origin app — no journey
 * state, fresh context per test. These pin the serving model itself
 * (architecture.md §Process model): one process on :8001 serving /api/* and
 * the styled static export at /app/*. Phase 6: `GET /` no longer redirects —
 * it serves the public landing page HTML directly (api.md §`GET /`), and the
 * admin console lives at /app/admin/.
 */

test.describe('smoke: single origin, health, styled render', () => {
  test('GET /api/health reports ok after a real DB check', async ({ request }) => {
    const res = await request.get(`${ORIGIN}/api/health`);
    expect(res.status()).toBe(200);
    // Exact success envelope (api.md §Conventions + §Health).
    expect(await res.json()).toEqual({ data: { status: 'ok', db: 'ok' }, error: null });
  });

  test('the root URL serves the landing page HTML directly (no redirect)', async ({ page }) => {
    const res = await page.goto(`${ORIGIN}/`);
    expect(res?.status()).toBe(200);
    expect(new URL(page.url()).pathname).toBe('/');
  });

  test('Admin Home loads styled, gated by the access-key card', async ({ page }) => {
    await page.goto(`${ADMIN_BASE}/`);

    // Fresh context (no stored key) → the access-key card is the entry state.
    const keyInput = page.getByTestId('admin-key-input');
    await expect(keyInput).toBeVisible();
    await expect(keyInput).toHaveAttribute('type', 'password');
    await expect(page.getByTestId('admin-key-submit')).toBeVisible();

    // Styled render, not a bare-HTML fallback: a stylesheet is attached and the
    // body font is the design-system stack, not the browser default serif.
    const styleSheetCount = await page.evaluate(() => document.styleSheets.length);
    expect(styleSheetCount).toBeGreaterThan(0);
    const fontFamily = await page.evaluate(() => getComputedStyle(document.body).fontFamily);
    expect(fontFamily.toLowerCase()).not.toContain('times');
  });
});
