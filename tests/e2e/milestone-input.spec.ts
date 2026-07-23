import { test, expect } from '@playwright/test';
import { APP_BASE, ORIGIN, adminKey } from './helpers';

/**
 * A milestone that requires a GitHub URL: the participant can't complete it
 * until a valid URL is entered, and the facilitator sees the submitted value.
 */
test('milestone input gates completion and surfaces submissions', async ({ browser, request }) => {
  const created = await request.post(`${ORIGIN}/api/admin/workshops`, {
    headers: { 'X-Admin-Key': adminKey() },
    data: {
      name: `E2E Milestone Input ${Date.now()}`,
      milestones: [
        {
          title: 'Push your repo',
          content_md: 'Share your repo link.',
          minutes: null,
          input_config: { type: 'github_url', label: 'Your repo URL' },
        },
      ],
    },
  });
  const ws = (await created.json()).data.workshop;

  const partCtx = await browser.newContext();
  const part = await partCtx.newPage();
  await part.goto(`${APP_BASE}/join/?s=${ws.join_slug}`);
  await part.getByTestId('join-name-input').fill('Asha');
  await part.getByTestId('join-submit').click();
  await expect(part.getByTestId('tracker-page')).toBeVisible({ timeout: 15_000 });

  const item = part.getByTestId('milestone-item').first();
  // The gated field is visible; the checkbox can't be ticked directly.
  await expect(item.getByTestId('milestone-input')).toBeVisible();
  await expect(item.getByTestId('milestone-toggle')).toBeDisabled();

  // A non-GitHub URL keeps the complete button disabled.
  await item.getByTestId('milestone-input').fill('https://example.com/x');
  await expect(item.getByTestId('milestone-complete-gated')).toBeDisabled();

  // A valid GitHub URL enables completion.
  await item.getByTestId('milestone-input').fill('https://github.com/asha/lab');
  await item.getByTestId('milestone-complete-gated').click();
  await expect(item.getByTestId('milestone-toggle')).toBeChecked({ timeout: 10_000 });

  // The facilitator sees the submitted URL.
  const fac = await (await browser.newContext()).newPage();
  await fac.goto(`${APP_BASE}/f/?t=${encodeURIComponent(ws.admin_token)}`);
  await expect(fac.getByTestId('dashboard-page')).toBeVisible();
  const submissions = fac.getByTestId('milestone-submissions');
  await expect(submissions).toContainText('Asha', { timeout: 15_000 });
  await expect(submissions).toContainText('github.com/asha/lab');

  // CSV export includes the participant, their progress, and the submitted URL.
  const download = fac.waitForEvent('download');
  await fac.getByTestId('participant-export-csv').click();
  const path = await (await download).path();
  const fs = await import('node:fs');
  const csv = fs.readFileSync(path, 'utf8');
  expect(csv).toContain('Name');
  expect(csv).toContain('Asha');
  expect(csv).toContain('https://github.com/asha/lab');
});
