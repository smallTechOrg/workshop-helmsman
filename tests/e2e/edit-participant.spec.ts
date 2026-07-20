import { test, expect } from '@playwright/test';
import { APP_BASE, ORIGIN, adminKey } from './helpers';

/**
 * Facilitator edits a participant's name + custom answers from the dashboard.
 * Seeds via the API (a workshop with a dropdown join field + one joined
 * participant), then drives the edit modal in the browser and asserts the
 * change lands on the participant table.
 */
test('facilitator edits a participant name and answer from the dashboard', async ({
  page,
  request,
}) => {
  const created = await request.post(`${ORIGIN}/api/admin/workshops`, {
    headers: { 'X-Admin-Key': adminKey() },
    data: {
      name: `E2E Edit Participant ${Date.now()}`,
      milestones: [{ title: 'M1', content_md: 'x', minutes: 5 }],
      join_form: [
        {
          key: 'team',
          type: 'dropdown',
          label: 'Team',
          required: true,
          options: ['Platform', 'Growth'],
        },
      ],
    },
  });
  expect(created.ok()).toBeTruthy();
  const ws = (await created.json()).data.workshop;

  const joined = await request.post(`${ORIGIN}/api/join/${ws.join_slug}`, {
    data: { name: 'Original Name', answers: { team: 'Platform' } },
  });
  expect(joined.ok()).toBeTruthy();

  // Open the facilitator dashboard.
  await page.goto(`${APP_BASE}/f/?t=${encodeURIComponent(ws.admin_token)}`);
  await expect(page.getByTestId('dashboard-page')).toBeVisible();
  const row = page.getByTestId('participant-row').filter({ hasText: 'Original Name' });
  await expect(row).toHaveCount(1, { timeout: 15_000 });

  // Open the edit modal, change the name and the dropdown answer.
  await row.getByTestId('participant-edit').click();
  const nameInput = page.getByTestId('edit-participant-name');
  await expect(nameInput).toHaveValue('Original Name');
  await nameInput.fill('Renamed Person');
  await page.getByTestId('edit-participant-field-team').selectOption('Growth');

  const saved = page.waitForResponse(
    (r) =>
      /\/api\/f\/[^/]+\/participants\/\d+$/.test(r.url().split('?')[0]) &&
      r.request().method() === 'PATCH',
  );
  await page.getByTestId('edit-participant-save').click();
  expect((await saved).ok()).toBeTruthy();

  // The table reflects the new name and answer within one poll.
  await expect(async () => {
    const renamed = page.getByTestId('participant-row').filter({ hasText: 'Renamed Person' });
    await expect(renamed).toHaveCount(1);
    await expect(renamed).toContainText('Growth');
  }).toPass({ timeout: 10_000 });
  await expect(
    page.getByTestId('participant-row').filter({ hasText: 'Original Name' }),
  ).toHaveCount(0);
});
