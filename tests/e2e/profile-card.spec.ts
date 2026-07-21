import { test, expect } from '@playwright/test';
import { APP_BASE, ORIGIN, adminKey } from './helpers';

/**
 * The participant's own profile card: it shows their name + custom answers and
 * the personal link, and lets them edit their details in place. Seeds a
 * workshop with a dropdown join field via the API, joins in the browser, then
 * drives the edit modal and asserts the change lands on the card.
 */
test('participant sees and edits their own profile card', async ({ page, request }) => {
  const created = await request.post(`${ORIGIN}/api/admin/workshops`, {
    headers: { 'X-Admin-Key': adminKey() },
    data: {
      name: `E2E Profile Card ${Date.now()}`,
      milestones: [{ title: 'M1', content_md: 'x', minutes: 5 }],
      join_form: [
        { key: 'team', type: 'dropdown', label: 'Team', required: true, options: ['Platform', 'Growth'] },
      ],
    },
  });
  const ws = (await created.json()).data.workshop;

  await page.goto(`${APP_BASE}/join/?s=${ws.join_slug}`);
  await page.getByTestId('join-name-input').fill('Asha');
  await page.getByTestId('join-field-team').selectOption('Platform');
  await page.getByTestId('join-submit').click();
  await expect(page.getByTestId('tracker-page')).toBeVisible({ timeout: 15_000 });

  // The card shows the name, the custom answer, and the personal link.
  const card = page.getByTestId('profile-card');
  await expect(card).toContainText('Asha');
  await expect(card).toContainText('Platform');
  await expect(card.getByTestId('personal-link')).toContainText('/p/');

  // Edit name + answer.
  await page.getByTestId('profile-edit').click();
  const nameInput = page.getByTestId('profile-name-input');
  await expect(nameInput).toHaveValue('Asha');
  await nameInput.fill('Asha K.');
  await page.getByTestId('profile-field-team').selectOption('Growth');

  const saved = page.waitForResponse(
    (r) => /\/api\/p\/[^/]+\/profile$/.test(r.url().split('?')[0]) && r.request().method() === 'PATCH',
  );
  await page.getByTestId('profile-save').click();
  expect((await saved).ok()).toBeTruthy();

  await expect(async () => {
    await expect(card).toContainText('Asha K.');
    await expect(card).toContainText('Growth');
  }).toPass({ timeout: 10_000 });
});
