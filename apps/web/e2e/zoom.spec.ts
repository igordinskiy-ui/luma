import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

const dashboard = {
  phase: 'quit', paused_from: null, remaining: 0, cigarettes_per_pack: 20, pack_price: 240,
  smoke_free_seconds: 90000, best_smoke_free_seconds: 172800, attempt_number: 2,
  next_milestone_seconds: 259200, next_milestone_label: '3 дня', avoided_cigarettes: 18, saved_money: 216,
  risk: 'low', intervention: 'Следующий честный шаг.', reasons: 'Хочу легче начинать утро.', recent_triggers: [],
  preparation_steps: [], recovery_until: null, recovery_steps: [], target_quit_at: null,
};

test('@zoom public and app screens reflow at the 320px equivalent of 200% zoom', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);

  await page.addInitScript(() => {
    sessionStorage.setItem('kurilka-access-token', 'zoom-e2e-token');
    sessionStorage.setItem('kurilka-user-id', '42');
  });
  await page.route('**/api/v1/bootstrap', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ age_confirmed: true, consent_current: true, onboarded: true }) }));
  await page.route('**/api/v1/dashboard', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(dashboard) }));
  await page.goto('/app');
  await expect(page.getByRole('heading', { name: 'Твой путь продолжается', level: 1 })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
  expect((await new AxeBuilder({ page }).include('.path-app-shell').analyze()).violations).toEqual([]);
});
