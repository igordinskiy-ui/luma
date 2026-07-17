import { expect, Page, test } from '@playwright/test';

const dashboard = {
  phase: 'last_pack', paused_from: null, remaining: 7, cigarettes_per_pack: 20, pack_price: 240,
  smoke_free_seconds: 0, best_smoke_free_seconds: 172800, attempt_number: 2,
  next_milestone_seconds: null, next_milestone_label: null, avoided_cigarettes: 0, saved_money: 0,
  risk: 'low', intervention: 'Выбери следующий маленький шаг.', reasons: 'Хочу легче начинать утро.',
  recent_triggers: ['coffee'], preparation_steps: [], recovery_until: null, recovery_steps: [], target_quit_at: null,
};

test.beforeEach(async ({ page }) => {
  await page.clock.setFixedTime(new Date('2026-07-17T09:30:00+03:00'));
});

async function stabilize(page: Page) {
  await page.addStyleTag({ content: `
    *, *::before, *::after { animation: none !important; transition: none !important; caret-color: transparent !important; }
    html { scroll-behavior: auto !important; }
  ` });
}

test('visual baseline — public Path landing', async ({ page }) => {
  await page.route('**/api/v1/launch-status', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ public_launch_enabled: true }) }));
  await page.goto('/');
  await stabilize(page);
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Следующий честный шаг');
  await expect(page.getByRole('link', { name: /Войти через Telegram/ })).toBeVisible();
  await expect(page).toHaveScreenshot('path-landing.png', { fullPage: true });
});

test('visual baseline — last-pack dashboard', async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.setItem('kurilka-access-token', 'visual-regression-token');
    sessionStorage.setItem('kurilka-user-id', '42');
  });
  await page.route('**/api/v1/bootstrap', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ age_confirmed: true, consent_current: true, onboarded: true }) }));
  await page.route('**/api/v1/dashboard', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(dashboard) }));
  await page.goto('/app');
  await stabilize(page);
  await expect(page.getByRole('heading', { name: 'Осталось 7' })).toBeVisible();
  await expect(page).toHaveScreenshot('path-dashboard-last-pack.png');
});
