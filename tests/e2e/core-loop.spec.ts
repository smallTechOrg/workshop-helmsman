import {
  test,
  expect,
  type BrowserContext,
  type Locator,
  type Page,
} from '@playwright/test';
import { APP_BASE, adminKey, extractUrl } from './helpers';

/**
 * Phase 1 core live loop — one serial journey against the live single-origin
 * app (spec/roadmap.md §Phase 1 gate paragraph):
 *
 *   create workshop (3 milestones incl. a code block) → join as two
 *   participants in separate contexts → tracker renders styled markdown →
 *   mark complete → dashboard reflects it within one poll → help request →
 *   answer from queue → answer visible on tracker → participant resolves →
 *   browser reload restores state (cookie) → personal link opens identical
 *   state in a fresh context (cross-device) → labelled stubs are visible and
 *   non-interactive.
 *
 * Every run creates a FRESH workshop (timestamped name) — no pre-existing
 * data is assumed. Live-update waits use polling assertions sized to one poll
 * cycle (dashboard 2 s / tracker 3 s vs. 10 s expect timeout) — never sleeps.
 */

const WORKSHOP_NAME = `E2E Core Loop ${Date.now()}`;

const M1_TITLE = 'Set up your environment';
const M2_TITLE = 'Call the health endpoint';
const M3_TITLE = 'Ship it';

const M1_CONTENT = [
  'Install the dependencies, then verify your shell works:',
  '',
  '```bash',
  'echo "hello"',
  '```',
  '',
  'If anything fails, read the [FastAPI docs](https://fastapi.tiangolo.com/) before asking for help.',
].join('\n');
const M2_CONTENT = 'Use `curl` to hit `/api/health` and confirm the response says ok.';
const M3_CONTENT = 'Push your branch and open a pull request.';

const HELP_MESSAGE = `I am getting a 401 from the API - what should I check? (run ${Date.now()})`;
const ANSWER_MD = [
  'Check your `.env` file first:',
  '',
  '```bash',
  'grep API_KEY .env',
  '```',
  '',
  'Then restart the server.',
].join('\n');

let facCtx: BrowserContext;
let priyaCtx: BrowserContext;
let marcoCtx: BrowserContext;
let deviceCtx: BrowserContext;
let fac: Page;
let priya: Page;
let marco: Page;
let device3: Page;

let joinUrl = '';
let dashboardUrl = '';
let personalUrl = '';

const uncaughtErrors: Array<{ page: string; message: string }> = [];

/**
 * A completed milestone's toggle must expose real checked semantics
 * (capabilities.md design system: semantic HTML, keyboard-reachable).
 * Accepts a native checkbox (the toggle itself or a descendant), aria-checked,
 * or aria-pressed.
 */
async function expectToggleCompleted(milestoneItem: Locator): Promise<void> {
  const toggle = milestoneItem.getByTestId('milestone-toggle');
  await expect(async () => {
    const ariaChecked = await toggle.getAttribute('aria-checked');
    const ariaPressed = await toggle.getAttribute('aria-pressed');
    const selfChecked = await toggle.isChecked().catch(() => null);
    const innerBox = toggle.locator('input[type="checkbox"]').first();
    const innerChecked = (await innerBox.count()) > 0 ? await innerBox.isChecked() : null;
    const completed =
      ariaChecked === 'true' || ariaPressed === 'true' || selfChecked === true || innerChecked === true;
    if (!completed) {
      throw new Error('milestone-toggle does not report a completed/checked state');
    }
  }).toPass({ timeout: 10_000 });
}

/** Priya has 1 of 3 done — accept "1 / 3" text, a 33% bar, or aria-valuenow. */
async function expectProgressOneOfThree(page: Page): Promise<void> {
  const bar = page.getByTestId('progress-bar').first();
  await expect(async () => {
    const barText = (await bar.textContent().catch(() => '')) ?? '';
    const aria = await bar.getAttribute('aria-valuenow').catch(() => null);
    const headerText = await page.getByTestId('tracker-page').innerText();
    const ok =
      /1\s*\/\s*3|\b33\b/.test(barText) ||
      (aria !== null && [1, 33].includes(Math.round(Number(aria)))) ||
      /1\s*\/\s*3/.test(headerText);
    if (!ok) throw new Error('progress does not reflect 1 / 3 yet');
  }).toPass({ timeout: 10_000 });
}

test.describe.serial('Phase 1 — core live loop', () => {
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
    ({ ctx: priyaCtx, page: priya } = await mk('priya'));
    ({ ctx: marcoCtx, page: marco } = await mk('marco'));
    ({ ctx: deviceCtx, page: device3 } = await mk('third-device'));
  });

  test.afterAll(async () => {
    await Promise.all(
      [facCtx, priyaCtx, marcoCtx, deviceCtx].filter(Boolean).map((ctx) => ctx.close()),
    );
  });

  test('facilitator signs in, creates a 3-milestone workshop, opens the live dashboard', async () => {
    await fac.goto(`${APP_BASE}/`);
    await fac.getByTestId('admin-key-input').fill(adminKey());
    await fac.getByTestId('admin-key-submit').click();
    await expect(fac.getByTestId('new-workshop-button')).toBeVisible();

    await fac.getByTestId('new-workshop-button').click();
    await fac.getByTestId('workshop-name-input').fill(WORKSHOP_NAME);

    // Add milestone editor rows until there are exactly three.
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

    // The workshop card (with both share links) must be reachable — either the
    // app returns to the list itself, or a reload of Admin Home shows it.
    const card = fac.getByTestId('workshop-card').filter({ hasText: WORKSHOP_NAME }).first();
    await expect(async () => {
      if (!(await card.isVisible())) {
        await fac.goto(`${APP_BASE}/`);
      }
      await expect(card).toBeVisible({ timeout: 4000 });
    }).toPass({ timeout: 30_000 });

    joinUrl = extractUrl(await card.getByTestId('join-link').innerText(), '/j/');
    dashboardUrl = extractUrl(await card.getByTestId('facilitator-link').innerText(), '/f/');
    expect(joinUrl).toMatch(/\/j\/[A-Za-z0-9_-]{6,}$/);
    expect(dashboardUrl).toMatch(/\/f\/[A-Za-z0-9_-]{20,}$/);

    // Pretty facilitator link redirects into the static app, dashboard loads.
    await fac.goto(dashboardUrl);
    await expect(fac).toHaveURL(/\/app\/f\/\?t=[A-Za-z0-9_-]+/);
    const dashboard = fac.getByTestId('dashboard-page');
    await expect(dashboard).toBeVisible();
    await expect(dashboard).toContainText(WORKSHOP_NAME);
    await expect(fac.getByTestId('milestone-stat')).toHaveCount(3);
    // Milestone titles appear on the dashboard (per-milestone completion bars,
    // capabilities.md C3). The testid contract only guarantees the completion
    // COUNT lives inside milestone-stat, so titles are asserted page-level.
    await expect(dashboard).toContainText(M1_TITLE);
    await expect(dashboard).toContainText(M2_TITLE);
    await expect(dashboard).toContainText(M3_TITLE);
    // Help-queue empty state (capabilities.md C4) before anyone asks.
    await expect(fac.getByTestId('help-queue')).toContainText(/no open help requests/i);
    // Dashboard stays open from here on — later tests assert its live updates.
  });

  test('Priya joins via the pretty link and sees rendered milestone markdown', async () => {
    await priya.goto(joinUrl);
    await expect(priya).toHaveURL(/\/app\/join\/\?s=[A-Za-z0-9_-]+/);
    await expect(priya.getByText(WORKSHOP_NAME).first()).toBeVisible();

    await priya.getByTestId('join-name-input').fill('Priya');
    const joined = priya.waitForResponse(
      (r) => /\/api\/join\/[^/?]+$/.test(r.url().split('?')[0]) && r.request().method() === 'POST',
    );
    await priya.getByTestId('join-submit').click();
    expect((await joined).ok(), 'POST /api/join/{slug} must succeed').toBeTruthy();

    await expect(priya.getByTestId('tracker-page')).toBeVisible({ timeout: 15_000 });
    // Client-side navigation to the tracker route — `t` may sit anywhere in
    // the query string (only server 307s have a spec-exact URL shape).
    await expect(priya).toHaveURL(/\/app\/p\/.*[?&]t=[A-Za-z0-9_-]+/);

    const items = priya.getByTestId('milestone-item');
    await expect(items).toHaveCount(3);
    await expect(items.nth(0)).toContainText(M1_TITLE);
    await expect(items.nth(1)).toContainText(M2_TITLE);
    await expect(items.nth(2)).toContainText(M3_TITLE);

    // Milestone 1 is the current milestone (auto-expanded): its markdown body
    // must be RENDERED — a highlighted <pre><code>, not raw backticks.
    const codeBlock = items.first().locator('pre code');
    await expect(codeBlock).toBeVisible();
    await expect(codeBlock).toContainText('echo "hello"');
    await expect(codeBlock).toHaveClass(/language-|hljs/);
    await expect(items.first()).not.toContainText('```');

    const docsLink = items.first().getByRole('link', { name: 'FastAPI docs' });
    await expect(docsLink).toBeVisible();
    await expect(docsLink).toHaveAttribute('href', 'https://fastapi.tiangolo.com/');

    // Help panel empty state (capabilities.md C4).
    await expect(priya.getByTestId('tracker-page')).toContainText(/ask here/i);

    // Capture the cross-device personal link now (the callout is one-time).
    await expect(priya.getByTestId('personal-link')).toBeVisible();
    personalUrl = extractUrl(await priya.getByTestId('personal-link').innerText(), '/p/');
    expect(personalUrl).toMatch(/\/p\/[A-Za-z0-9_-]{16,}$/);
  });

  test('Marco joins in a second context; the room updates live everywhere', async () => {
    await marco.goto(joinUrl);
    await expect(marco).toHaveURL(/\/app\/join\/\?s=[A-Za-z0-9_-]+/);
    await marco.getByTestId('join-name-input').fill('Marco');
    const joined = marco.waitForResponse(
      (r) => /\/api\/join\/[^/?]+$/.test(r.url().split('?')[0]) && r.request().method() === 'POST',
    );
    await marco.getByTestId('join-submit').click();
    expect((await joined).ok(), 'POST /api/join/{slug} must succeed').toBeTruthy();
    await expect(marco.getByTestId('tracker-page')).toBeVisible({ timeout: 15_000 });
    await expect(marco.getByTestId('milestone-item')).toHaveCount(3);

    // Both participants appear on every surface within one poll cycle.
    await expect(marco.getByTestId('leaderboard')).toContainText('Priya');
    await expect(priya.getByTestId('leaderboard')).toContainText('Marco', { timeout: 15_000 });
    await expect(fac.getByTestId('participant-row')).toHaveCount(2, { timeout: 15_000 });
    await expect(fac.getByTestId('participant-row').filter({ hasText: 'Priya' })).toHaveCount(1);
    await expect(fac.getByTestId('participant-row').filter({ hasText: 'Marco' })).toHaveCount(1);
  });

  test("Priya's completion moves her progress bar and the live dashboard within one poll", async () => {
    // Before: nobody has completed milestone 1.
    const firstStat = fac.getByTestId('milestone-stat').first();
    await expect(firstStat).toContainText(/\b0\b/);
    const statBefore = (await firstStat.innerText()).replace(/\s+/g, ' ').trim();

    const firstItem = priya.getByTestId('milestone-item').first();
    const completed = priya.waitForResponse(
      (r) =>
        /\/milestones\/\d+\/complete$/.test(r.url().split('?')[0]) &&
        r.request().method() === 'POST',
    );
    await firstItem.getByTestId('milestone-toggle').click();
    expect((await completed).ok(), 'complete endpoint must succeed').toBeTruthy();

    await expectProgressOneOfThree(priya);
    await expectToggleCompleted(firstItem);

    // Live dashboard (already open, 2 s poll): the first milestone stat's text
    // CHANGES and now carries the completion ("1" count and/or "50%"). Change
    // detection guards against a "1" that was already present before the
    // completion (e.g. a "1." position marker in the stat row).
    await expect(async () => {
      const now = (await firstStat.innerText()).replace(/\s+/g, ' ').trim();
      expect(now).not.toBe(statBefore);
      expect(now).toMatch(/\b1\b|50/);
    }).toPass({ timeout: 10_000 });
    const priyaRow = fac.getByTestId('participant-row').filter({ hasText: 'Priya' }).first();
    await expect(priyaRow.getByTestId('participant-progress')).toContainText(/\b1\b|33/, {
      timeout: 10_000,
    });
  });

  test('help request → facilitator markdown answer → resolve, live on both sides', async () => {
    // Priya asks for help.
    await priya.getByTestId('help-input').fill(HELP_MESSAGE);
    const helpPosted = priya.waitForResponse(
      (r) => /\/api\/p\/[^/]+\/help$/.test(r.url().split('?')[0]) && r.request().method() === 'POST',
    );
    await priya.getByTestId('help-submit').click();
    expect((await helpPosted).ok(), 'POST …/help must succeed').toBeTruthy();

    const myItem = priya.getByTestId('help-item').filter({ hasText: HELP_MESSAGE }).first();
    await expect(myItem).toBeVisible();
    await expect(myItem.getByTestId('help-status')).toContainText(/open|waiting/i);

    // Queue card appears on the dashboard within one poll, with name, message
    // and her CURRENT milestone (milestone 2, after completing milestone 1).
    const queueItem = fac.getByTestId('help-queue-item').filter({ hasText: HELP_MESSAGE }).first();
    await expect(queueItem).toBeVisible({ timeout: 10_000 });
    await expect(queueItem).toContainText('Priya');
    await expect(queueItem).toContainText(M2_TITLE);

    // Facilitator answers with markdown containing a fenced code block.
    await queueItem.getByTestId('help-answer-input').fill(ANSWER_MD);
    const answered = fac.waitForResponse(
      (r) => /\/help\/\d+\/answer$/.test(r.url().split('?')[0]) && r.request().method() === 'POST',
    );
    await queueItem.getByTestId('help-answer-submit').click();
    expect((await answered).ok(), 'POST …/answer must succeed').toBeTruthy();

    // Priya sees the RENDERED answer within one tracker poll.
    const answer = myItem.getByTestId('help-answer').first();
    await expect(answer).toBeVisible({ timeout: 10_000 });
    await expect(answer).toContainText('Check your');
    const answerCode = answer.locator('pre code');
    await expect(answerCode).toBeVisible();
    await expect(answerCode).toContainText('grep API_KEY .env');
    await expect(answer).not.toContainText('```');
    await expect(myItem.getByTestId('help-status')).toContainText(/answered/i);

    // Priya resolves her own request.
    const resolved = priya.waitForResponse(
      (r) => /\/help\/\d+\/resolve$/.test(r.url().split('?')[0]) && r.request().method() === 'POST',
    );
    await myItem.getByTestId('help-resolve').click();
    expect((await resolved).ok(), 'POST …/resolve must succeed').toBeTruthy();
    await expect(myItem.getByTestId('help-status')).toContainText(/resolved/i, { timeout: 10_000 });

    // Dashboard reflects resolution within one poll: the card either shows a
    // resolved state or moves into the collapsed Resolved section (both are
    // spec-correct — capabilities.md collapses resolved requests).
    await expect(async () => {
      const item = fac.getByTestId('help-queue-item').filter({ hasText: HELP_MESSAGE }).first();
      const stillVisible = await item.isVisible().catch(() => false);
      if (stillVisible) {
        const text = (await item.innerText()).toLowerCase();
        if (!text.includes('resolved')) {
          throw new Error('help queue card is visible but not marked resolved yet');
        }
      }
    }).toPass({ timeout: 15_000 });
  });

  test('cookie auto-resume: reopening the join link recognizes Priya', async () => {
    // Same context (cookie jar intact) — the join page must recognize her and
    // forward to the tracker instead of showing a fresh join form.
    await priya.goto(joinUrl);
    await expect(priya).toHaveURL(/\/app\/p\/.*[?&]t=[A-Za-z0-9_-]+/, { timeout: 15_000 });
    await expect(priya.getByTestId('tracker-page')).toBeVisible();
    await expect(priya.getByTestId('join-name-input')).toHaveCount(0);
    await expect(priya.getByTestId('milestone-item')).toHaveCount(3);
    await expectProgressOneOfThree(priya);
    await expectToggleCompleted(priya.getByTestId('milestone-item').first());
    await expect(priya.getByTestId('leaderboard')).toContainText('Priya');
  });

  test('personal link opens identical state in a fresh third context (cross-device)', async () => {
    // Fresh context, zero cookies — the personal link IS the credential.
    await device3.goto(personalUrl);
    await expect(device3).toHaveURL(/\/app\/p\/\?t=[A-Za-z0-9_-]+/);
    await expect(device3.getByTestId('tracker-page')).toBeVisible({ timeout: 15_000 });
    await expect(device3.getByTestId('milestone-item')).toHaveCount(3);

    await expectProgressOneOfThree(device3);
    await expectToggleCompleted(device3.getByTestId('milestone-item').first());
    await expect(device3.getByTestId('leaderboard')).toContainText('Priya');
    await expect(device3.getByTestId('leaderboard')).toContainText('Marco');

    // The resolved help request travels with her, answer and all. Resolved
    // threads collapse by default (to keep the leaderboard in view) — expand it.
    const item = device3.getByTestId('help-item').filter({ hasText: HELP_MESSAGE }).first();
    await expect(item).toBeVisible();
    await expect(item.getByTestId('help-status')).toContainText(/resolved/i);
    await item.getByTestId('help-thread-toggle').click();
    const answerCode = item.getByTestId('help-answer').first().locator('pre code');
    await expect(answerCode).toBeVisible();
    await expect(answerCode).toContainText('grep API_KEY .env');
  });

  test('reload restores full tracker state', async () => {
    await priya.reload();
    await expect(priya.getByTestId('tracker-page')).toBeVisible({ timeout: 15_000 });
    await expect(priya.getByTestId('milestone-item')).toHaveCount(3);
    await expectProgressOneOfThree(priya);
    await expect(priya.getByTestId('leaderboard')).toContainText('Marco');
    const item = priya.getByTestId('help-item').filter({ hasText: HELP_MESSAGE }).first();
    await expect(item).toBeVisible();
    await expect(item.getByTestId('help-status')).toContainText(/resolved/i);
  });

  test('labelled stubs are visible and non-interactive on both live pages', async () => {
    const surfaces: Array<[string, Page, string]> = [
      ['dashboard', fac, 'dashboard-page'],
      ['tracker', priya, 'tracker-page'],
    ];
    for (const [label, page, rootId] of surfaces) {
      const labelled = page.getByTestId('stub-badge').filter({ hasText: /later phase/i });
      await expect(
        labelled.first(),
        `${label}: at least one stub-badge naming a later phase must be visible`,
      ).toBeVisible();

      const errorsBefore = uncaughtErrors.length;
      const urlBefore = page.url();
      let navigated = false;
      const onNav = () => {
        navigated = true;
      };
      page.on('framenavigated', onNav);
      // Disabled/inert controls legitimately reject the click — that IS the
      // pass condition, so a rejection is swallowed.
      await labelled
        .first()
        .click({ force: true, timeout: 3000 })
        .catch(() => undefined);
      // Every control INSIDE the stub must be non-interactive too: disabled,
      // aria-disabled, or inert under a force-click.
      const controls = labelled
        .first()
        .locator('button, a, input, [role="button"], [role="switch"]');
      const controlCount = await controls.count();
      for (let i = 0; i < controlCount; i += 1) {
        const control = controls.nth(i);
        const disabled = await control.isDisabled().catch(() => false);
        const ariaDisabled =
          (await control.getAttribute('aria-disabled').catch(() => null)) === 'true';
        if (!disabled && !ariaDisabled) {
          await control.click({ force: true, timeout: 3000 }).catch(() => undefined);
        }
      }
      // Short observation window for the ABSENCE of navigation/errors after
      // the clicks (not a live-update wait — polling assertions cannot observe
      // "nothing happened").
      await page.waitForTimeout(750);
      page.off('framenavigated', onNav);

      expect(navigated, `${label}: clicking a stub must not navigate`).toBe(false);
      expect(page.url(), `${label}: URL must be unchanged after clicking a stub`).toBe(urlBefore);
      expect(
        uncaughtErrors.length,
        `${label}: clicking a stub must not throw a page error`,
      ).toBe(errorsBefore);
      await expect(page.getByTestId(rootId)).toBeVisible();
    }
  });

  test('no uncaught page errors across the whole journey', async () => {
    const detail = uncaughtErrors.map((e) => `[${e.page}] ${e.message}`).join('\n');
    expect(uncaughtErrors, detail || 'clean').toEqual([]);
  });
});
