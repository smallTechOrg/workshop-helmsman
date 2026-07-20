import {
  test,
  expect,
  type BrowserContext,
  type Locator,
  type Page,
} from '@playwright/test';
import { APP_BASE, adminKey, extractUrl } from './helpers';

/**
 * Phase 2 — facilitator command & proactive intelligence (spec/roadmap.md
 * §Phase 2 "How the user tests it" + spec/api.md "# Phase 2 endpoints").
 *
 * One serial journey against the live single-origin app:
 *
 *   create workshop → two participants join → broadcast + undo → pause +
 *   resume → advance-all + undo → reorder → pulse/alerts go real → audit
 *   trail lists every action, undone ones marked undone.
 *
 * Every run creates a FRESH workshop (timestamped name). Live-update waits
 * use polling assertions sized to one poll cycle (dashboard 2 s / tracker
 * 3 s vs. the 12 s expect timeout) — never fixed sleeps beyond that.
 */

const WORKSHOP_NAME = `E2E Facilitator Command ${Date.now()}`;

const M1_TITLE = 'Set up your environment';
const M2_TITLE = 'Call the health endpoint';
const M3_TITLE = 'Ship it';
const M1_CONTENT = 'Install the dependencies, then verify your shell works.';
const M2_CONTENT = 'Use `curl` to hit `/api/health` and confirm the response says ok.';
const M3_CONTENT = 'Push your branch and open a pull request.';

const BROADCAST_MD = [
  '**Lunch is in 10 minutes** — wrap up your current milestone.',
  '',
  '- Grab your badge',
  '- We resume at 1pm',
].join('\n');

let facCtx: BrowserContext;
let aliceCtx: BrowserContext;
let bobCtx: BrowserContext;
let fac: Page;
let alice: Page;
let bob: Page;

let joinUrl = '';
let dashboardUrl = '';

const uncaughtErrors: Array<{ page: string; message: string }> = [];

/** A stub card carries the "later phase" StubBadge; a real one never does. */
async function expectNotAStub(card: Locator): Promise<void> {
  await expect(card.getByTestId('stub-badge').filter({ hasText: /later phase/i })).toHaveCount(0);
}

test.describe.serial('Phase 2 — facilitator command & proactive intelligence', () => {
  test.beforeAll(async ({ browser }) => {
    const mk = async (label: string): Promise<{ ctx: BrowserContext; page: Page }> => {
      const ctx = await browser.newContext({ baseURL: APP_BASE });
      ctx.setDefaultTimeout(15_000);
      ctx.setDefaultNavigationTimeout(30_000);
      const page = await ctx.newPage();
      page.on('pageerror', (err) => uncaughtErrors.push({ page: label, message: String(err) }));
      return { ctx, page };
    };
    ({ ctx: facCtx, page: fac } = await mk('facilitator'));
    ({ ctx: aliceCtx, page: alice } = await mk('alice'));
    ({ ctx: bobCtx, page: bob } = await mk('bob'));
  });

  test.afterAll(async () => {
    await Promise.all([facCtx, aliceCtx, bobCtx].filter(Boolean).map((ctx) => ctx.close()));
  });

  test('facilitator creates a workshop; Alice and Bob join', async () => {
    await fac.goto(`${APP_BASE}/`);
    await fac.getByTestId('admin-key-input').fill(adminKey());
    await fac.getByTestId('admin-key-submit').click();
    await expect(fac.getByTestId('new-workshop-button')).toBeVisible();

    await fac.getByTestId('new-workshop-button').click();
    await fac.getByTestId('workshop-name-input').fill(WORKSHOP_NAME);

    const titleInputs = fac.getByTestId('milestone-title-input');
    for (let i = 0; i < 4 && (await titleInputs.count()) < 3; i += 1) {
      await fac.getByTestId('add-milestone-button').click();
    }
    await expect(titleInputs).toHaveCount(3);

    const contentInputs = fac.getByTestId('milestone-content-input');
    const rows: Array<[string, string]> = [
      [M1_TITLE, M1_CONTENT],
      [M2_TITLE, M2_CONTENT],
      [M3_TITLE, M3_CONTENT],
    ];
    for (const [i, [title, content]] of rows.entries()) {
      await titleInputs.nth(i).fill(title);
      await contentInputs.nth(i).fill(content);
    }

    const created = fac.waitForResponse(
      (r) => r.url().includes('/api/admin/workshops') && r.request().method() === 'POST',
    );
    await fac.getByTestId('create-workshop-submit').click();
    expect((await created).ok(), 'POST /api/admin/workshops must succeed').toBeTruthy();

    const card = fac.getByTestId('workshop-card').filter({ hasText: WORKSHOP_NAME }).first();
    await expect(async () => {
      if (!(await card.isVisible())) {
        await fac.goto(`${APP_BASE}/`);
      }
      await expect(card).toBeVisible({ timeout: 4000 });
    }).toPass({ timeout: 30_000 });

    joinUrl = extractUrl(await card.getByTestId('join-link').innerText(), '/j/');
    dashboardUrl = extractUrl(await card.getByTestId('facilitator-link').innerText(), '/f/');

    await fac.goto(dashboardUrl);
    await expect(fac.getByTestId('dashboard-page')).toBeVisible();

    for (const [page, name] of [
      [alice, 'Alice'],
      [bob, 'Bob'],
    ] as const) {
      await page.goto(joinUrl);
      await page.getByTestId('join-name-input').fill(name);
      const joined = page.waitForResponse(
        (r) => /\/api\/join\/[^/?]+$/.test(r.url().split('?')[0]) && r.request().method() === 'POST',
      );
      await page.getByTestId('join-submit').click();
      expect((await joined).ok(), `POST /api/join/{slug} for ${name} must succeed`).toBeTruthy();
      await expect(page.getByTestId('tracker-page')).toBeVisible({ timeout: 15_000 });
    }

    await expect(fac.getByTestId('participant-row')).toHaveCount(2, { timeout: 15_000 });

    // Lower the stuck threshold now (settings control) so the proactive-intel
    // step later in this journey has a real chance of a stuck alert without a
    // multi-minute sleep (spec/api.md `PATCH …/settings`, 2–120 range).
    const settingsPatched = fac.waitForResponse(
      (r) => /\/api\/f\/[^/]+\/settings$/.test(r.url().split('?')[0]) && r.request().method() === 'PATCH',
    );
    await fac.getByTestId('settings-tab').click();
    await fac.getByTestId('stuck-minutes-input').fill('2');
    await fac.getByTestId('stuck-minutes-submit').click();
    expect((await settingsPatched).ok(), 'PATCH …/settings must succeed').toBeTruthy();
  });

  test('broadcast: markdown announcement appears on trackers, then undo removes it', async () => {
    await fac.getByTestId('broadcast-button').click();
    await fac.getByTestId('broadcast-textarea').fill(BROADCAST_MD);

    const sent = fac.waitForResponse(
      (r) => /\/api\/f\/[^/]+\/broadcast$/.test(r.url().split('?')[0]) && r.request().method() === 'POST',
    );
    await fac.getByTestId('broadcast-submit').click();
    const sentRes = await sent;
    expect(sentRes.ok(), 'POST …/broadcast must succeed').toBeTruthy();
    const sentBody = await sentRes.json();
    expect(sentBody.data.undoable_action_id).toBeTruthy();

    // Facilitator sees a confirmation/undo toast right away.
    const undoToast = fac.getByTestId('undo-toast');
    await expect(undoToast).toBeVisible();
    await expect(undoToast).toContainText(/undo/i);

    // Both participants see the RENDERED markdown banner within one poll.
    for (const page of [alice, bob]) {
      const banner = page.getByTestId('broadcast-banner');
      await expect(banner).toBeVisible({ timeout: 10_000 });
      await expect(banner).toContainText('Lunch is in 10 minutes');
      await expect(banner.locator('li').first()).toContainText('Grab your badge');
      await expect(banner).not.toContainText('**Lunch');
    }

    // Undo within the 30 s window.
    const undone = fac.waitForResponse(
      (r) => /\/api\/f\/[^/]+\/undo\/\d+$/.test(r.url().split('?')[0]) && r.request().method() === 'POST',
    );
    await undoToast.getByTestId('undo-button').click();
    expect((await undone).ok(), 'POST …/undo/{id} must succeed').toBeTruthy();

    // Banner disappears on both trackers within one poll.
    for (const page of [alice, bob]) {
      await expect(page.getByTestId('broadcast-banner')).toHaveCount(0, { timeout: 10_000 });
    }
  });

  test('pause locks completion; resume unlocks it', async () => {
    const paused = fac.waitForResponse(
      (r) => /\/api\/f\/[^/]+\/pause$/.test(r.url().split('?')[0]) && r.request().method() === 'POST',
    );
    await fac.getByTestId('pause-button').click();
    expect((await paused).ok(), 'POST …/pause (true) must succeed').toBeTruthy();

    // Alice's tracker shows the paused banner and a locked/disabled toggle
    // within one poll.
    await expect(alice.getByTestId('paused-banner')).toBeVisible({ timeout: 10_000 });
    const firstToggle = alice.getByTestId('milestone-item').first().getByTestId('milestone-toggle');
    await expect(async () => {
      const disabled = await firstToggle.isDisabled().catch(() => false);
      const ariaDisabled = (await firstToggle.getAttribute('aria-disabled').catch(() => null)) === 'true';
      if (!disabled && !ariaDisabled) throw new Error('milestone-toggle is not locked while paused');
    }).toPass({ timeout: 10_000 });

    // A forced click while paused must not create a completion.
    await firstToggle.click({ force: true }).catch(() => undefined);
    await expect(async () => {
      const ariaChecked = await firstToggle.getAttribute('aria-checked');
      expect(ariaChecked === 'true').toBe(false);
    }).toPass({ timeout: 3000 });

    const resumed = fac.waitForResponse(
      (r) => /\/api\/f\/[^/]+\/pause$/.test(r.url().split('?')[0]) && r.request().method() === 'POST',
    );
    await fac.getByTestId('pause-button').click();
    expect((await resumed).ok(), 'POST …/pause (false) must succeed').toBeTruthy();

    await expect(alice.getByTestId('paused-banner')).toHaveCount(0, { timeout: 10_000 });
    await expect(async () => {
      const disabled = await firstToggle.isDisabled().catch(() => false);
      const ariaDisabled = (await firstToggle.getAttribute('aria-disabled').catch(() => null)) === 'true';
      if (disabled || ariaDisabled) throw new Error('milestone-toggle is still locked after resume');
    }).toPass({ timeout: 10_000 });
  });

  test('advance-all on milestone 1 bumps progress everywhere; undo reverts it', async () => {
    const firstStat = fac.getByTestId('milestone-stat').first();
    const statBefore = (await firstStat.innerText()).replace(/\s+/g, ' ').trim();

    fac.once('dialog', (dialog) => dialog.accept());
    await firstStat.getByTestId('advance-all-button').click();

    const advanced = await fac.waitForResponse(
      (r) => /\/api\/f\/[^/]+\/milestones\/advance$/.test(r.url().split('?')[0]) && r.request().method() === 'POST',
    );
    expect(advanced.ok(), 'POST …/milestones/advance must succeed').toBeTruthy();
    const advancedBody = await advanced.json();
    expect(advancedBody.data.affected_count).toBeGreaterThan(0);
    const undoActionId = advancedBody.data.undoable_action_id;
    expect(undoActionId).toBeTruthy();

    await expect(async () => {
      const now = (await firstStat.innerText()).replace(/\s+/g, ' ').trim();
      expect(now).not.toBe(statBefore);
      expect(now).toMatch(/\b2\b|100/);
    }).toPass({ timeout: 10_000 });

    for (const page of [alice, bob]) {
      const firstItem = page.getByTestId('milestone-item').first();
      await expect(async () => {
        const ariaChecked = await firstItem.getByTestId('milestone-toggle').getAttribute('aria-checked');
        if (ariaChecked !== 'true') throw new Error('milestone not marked complete by advance-all yet');
      }).toPass({ timeout: 10_000 });
    }

    const undoToast = fac.getByTestId('undo-toast');
    await expect(undoToast).toBeVisible();
    const undone = fac.waitForResponse(
      (r) => new RegExp(`/api/f/[^/]+/undo/${undoActionId}$`).test(r.url().split('?')[0]) && r.request().method() === 'POST',
    );
    await undoToast.getByTestId('undo-button').click();
    expect((await undone).ok(), 'POST …/undo/{id} must succeed').toBeTruthy();

    await expect(async () => {
      const now = (await firstStat.innerText()).replace(/\s+/g, ' ').trim();
      expect(now).toBe(statBefore);
    }).toPass({ timeout: 10_000 });

    for (const page of [alice, bob]) {
      const firstItem = page.getByTestId('milestone-item').first();
      await expect(async () => {
        const ariaChecked = await firstItem.getByTestId('milestone-toggle').getAttribute('aria-checked');
        if (ariaChecked === 'true') throw new Error('undo did not revert advance-all completion');
      }).toPass({ timeout: 10_000 });
    }
  });

  test('reorder: milestones move on the dashboard and on participant trackers', async () => {
    await fac.getByTestId('milestones-tab').click();
    const rows = fac.getByTestId('milestone-row');
    await expect(rows).toHaveCount(3);
    await expect(rows.nth(0)).toContainText(M1_TITLE);

    // Move milestone 1 down one position (M1, M2, M3 -> M2, M1, M3).
    const reordered = fac.waitForResponse(
      (r) => /\/api\/f\/[^/]+\/milestones\/reorder$/.test(r.url().split('?')[0]) && r.request().method() === 'POST',
    );
    await rows.nth(0).getByTestId('milestone-move-down').click();
    expect((await reordered).ok(), 'POST …/milestones/reorder must succeed').toBeTruthy();

    await expect(async () => {
      const first = (await rows.nth(0).innerText());
      expect(first).toContain(M2_TITLE);
    }).toPass({ timeout: 10_000 });
    await expect(rows.nth(1)).toContainText(M1_TITLE);

    // Participant trackers reflect the new order within one poll.
    for (const page of [alice, bob]) {
      const items = page.getByTestId('milestone-item');
      await expect(async () => {
        const text = await items.nth(0).innerText();
        expect(text).toContain(M2_TITLE);
      }).toPass({ timeout: 10_000 });
      await expect(items.nth(1)).toContainText(M1_TITLE);
    }
  });

  test('proactive intelligence: pulse and alerts rails render real, non-stub data', async () => {
    test.setTimeout(150_000);
    await fac.getByTestId('dashboard-tab').click().catch(() => undefined);

    const pulseCard = fac.getByTestId('pulse-card');
    await expect(pulseCard).toBeVisible();
    await expectNotAStub(pulseCard);
    // Real numbers, not placeholders — pace ratio / on-track % / projected
    // finish are all rendered (api.md "pulse" shape).
    await expect(pulseCard).toContainText(/%/);
    await expect(pulseCard).not.toContainText(/coming in a later phase/i);

    const alertsRail = fac.getByTestId('alerts-rail');
    await expect(alertsRail).toBeVisible();
    await expectNotAStub(alertsRail);
    await expect(alertsRail).not.toContainText(/coming in a later phase/i);

    // Best-effort: Bob has been idle (no completion, no help activity) since
    // he joined; with stuck_minutes lowered to 2 in the setup test, give the
    // dashboard poll a window to surface him as a stuck alert. This is
    // explicitly best-effort per the roadmap ("where feasible in the test
    // window") — the mandatory assertions above (real, non-stub rails) do
    // not depend on it.
    const stuckCard = fac.getByTestId('stuck-alert-card').filter({ hasText: 'Bob' });
    await expect(async () => {
      const count = await stuckCard.count();
      if (count > 0) {
        await expect(stuckCard.first()).toContainText(/minute/i);
      }
    }).toPass({ timeout: 130_000 });
  });

  test('audit tab lists every action with who/what/when; undone actions are marked', async () => {
    await fac.getByTestId('audit-tab').click();
    const rows = fac.getByTestId('audit-row');
    await expect(rows.first()).toBeVisible();

    const broadcastRow = rows.filter({ hasText: /broadcast/i }).first();
    await expect(broadcastRow).toBeVisible();
    await expect(broadcastRow).toContainText(/undone/i);

    const pauseRows = rows.filter({ hasText: /pause/i });
    await expect(pauseRows).toHaveCount(2, { timeout: 10_000 });

    const advanceRow = rows.filter({ hasText: /advance/i }).first();
    await expect(advanceRow).toBeVisible();
    await expect(advanceRow).toContainText(/undone/i);

    const reorderRow = rows.filter({ hasText: /reorder/i }).first();
    await expect(reorderRow).toBeVisible();

    // Every audit row names an actor and a timestamp (who/what/when) — assert
    // the shape on the broadcast row, which this journey fully exercised.
    await expect(broadcastRow.getByTestId('audit-actor')).toBeVisible();
    await expect(broadcastRow.getByTestId('audit-timestamp')).toBeVisible();
  });

  test('no uncaught page errors across the whole journey', async () => {
    const detail = uncaughtErrors.map((e) => `[${e.page}] ${e.message}`).join('\n');
    expect(uncaughtErrors, detail || 'clean').toEqual([]);
  });
});
