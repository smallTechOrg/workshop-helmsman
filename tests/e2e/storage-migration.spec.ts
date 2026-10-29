import { test, expect } from '@playwright/test';
import { ADMIN_BASE, LANDING_URL, adminKey } from './helpers';

/**
 * Workshop0 rename — one-release localStorage migrate-on-read fallback.
 * Pre-rename keys are still honoured, re-written under the new names, and
 * never deleted this release.
 */
const OLD_ADMIN = 'helmsman_admin_key'; // LEGACY-COMPAT
const OLD_LIST = 'helmsman_my_workshops'; // LEGACY-COMPAT

test.describe('legacy localStorage fallback', () => {
  test('old admin key keeps the facilitator signed in and is re-written under the new key', async ({
    page,
  }) => {
    await page.addInitScript(
      ([k, v]) => {
        if (!window.localStorage.getItem('workshop0_admin_key') && !window.sessionStorage.getItem('seeded')) {
          window.localStorage.setItem(k, v);
          window.sessionStorage.setItem('seeded', '1');
        }
      },
      [OLD_ADMIN, adminKey()],
    );
    await page.goto(`${ADMIN_BASE}/`);
    await expect(page.getByTestId('new-workshop-button')).toBeVisible();
    const stored = await page.evaluate(
      ([n, o]) => [localStorage.getItem(n), localStorage.getItem(o)],
      ['workshop0_admin_key', OLD_ADMIN],
    );
    expect(stored[0]).toBe(adminKey());
    expect(stored[1], 'old key is not deleted this release').toBe(adminKey());
  });

  test('old workshop list is shown on the landing page and re-written under the new key', async ({
    page,
  }) => {
    const entry = {
      name: 'Legacy Remembered Workshop',
      facilitator_url: 'http://localhost/app/f/?t=legacy',
      join_url: 'http://localhost/app/join/?c=legacy',
      created_at: new Date().toISOString(),
    };
    await page.goto(LANDING_URL);
    await page.evaluate(([k, v]) => localStorage.setItem(k, v), [OLD_LIST, JSON.stringify([entry])]);
    await page.reload();
    await expect(page.getByTestId('your-workshops')).toBeVisible();
    await expect(page.getByText('Legacy Remembered Workshop')).toBeVisible();
    const stored = await page.evaluate(
      ([n, o]) => [localStorage.getItem(n), localStorage.getItem(o)],
      ['workshop0_my_workshops', OLD_LIST],
    );
    expect(JSON.parse(stored[0] as string)[0].name).toBe(entry.name);
    expect(stored[1]).not.toBeNull();
  });
});
