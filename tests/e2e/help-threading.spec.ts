import { test, expect } from '@playwright/test';
import { APP_BASE, ORIGIN, adminKey } from './helpers';

/**
 * Threaded help desk: a participant asks, the facilitator replies, the
 * participant replies back (reopening the thread), then the room's shared
 * questions view shows the exchange. Drives both UIs in the browser.
 */
test('help thread: participant ↔ facilitator replies, reopen, and room view', async ({
  browser,
  request,
}) => {
  const created = await request.post(`${ORIGIN}/api/admin/workshops`, {
    headers: { 'X-Admin-Key': adminKey() },
    data: {
      name: `E2E Help Thread ${Date.now()}`,
      milestones: [{ title: 'M1', content_md: 'x', minutes: 5 }],
    },
  });
  const ws = (await created.json()).data.workshop;

  const facCtx = await browser.newContext();
  const partCtx = await browser.newContext();
  const fac = await facCtx.newPage();
  const part = await partCtx.newPage();

  // Participant joins and asks.
  await part.goto(`${APP_BASE}/join/?s=${ws.join_slug}`);
  await part.getByTestId('join-name-input').fill('Priya');
  await part.getByTestId('join-submit').click();
  await expect(part.getByTestId('tracker-page')).toBeVisible({ timeout: 15_000 });
  await part.getByTestId('help-input').fill('My setup script fails.');
  await part.getByTestId('help-submit').click();
  const item = part.getByTestId('help-item').first();
  await expect(item).toContainText('My setup script fails.');

  // Facilitator answers from the dashboard.
  await fac.goto(`${APP_BASE}/f/?t=${encodeURIComponent(ws.admin_token)}`);
  await expect(fac.getByTestId('dashboard-page')).toBeVisible();
  const qItem = fac.getByTestId('help-queue-item').filter({ hasText: 'setup script' });
  await expect(qItem).toHaveCount(1, { timeout: 15_000 });
  await qItem.getByTestId('help-answer-input').fill('Try `chmod +x setup.sh` first.');
  await qItem.getByTestId('help-answer-submit').click();

  // Participant sees the facilitator answer, then replies back.
  await expect(item.getByTestId('help-answer')).toContainText('chmod +x setup.sh', {
    timeout: 15_000,
  });
  await item.getByTestId('help-reply-input').fill('Still failing after that.');
  await item.getByTestId('help-reply-submit').click();
  await expect(item.getByTestId('help-reply-mine')).toContainText('Still failing after that.', {
    timeout: 10_000,
  });

  // The reply reopened the thread — facilitator queue shows it open again with
  // the participant's follow-up in the thread.
  await expect(qItem.getByTestId('help-participant-reply')).toContainText(
    'Still failing after that.',
    { timeout: 15_000 },
  );

  // A second participant can see the room's questions read-only.
  const part2 = await (await browser.newContext()).newPage();
  await part2.goto(`${APP_BASE}/join/?s=${ws.join_slug}`);
  await part2.getByTestId('join-name-input').fill('Sam');
  await part2.getByTestId('join-submit').click();
  await expect(part2.getByTestId('tracker-page')).toBeVisible({ timeout: 15_000 });
  await part2.getByTestId('room-questions-open').click();
  const roomList = part2.getByTestId('room-questions-list');
  await expect(roomList).toBeVisible({ timeout: 10_000 });
  await expect(roomList).toContainText('Priya');
  await expect(roomList).toContainText('My setup script fails.');
});
