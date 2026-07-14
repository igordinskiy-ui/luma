import AxeBuilder from '@axe-core/playwright';
import { expect, Page, test } from '@playwright/test';

const dashboard = {
  phase: 'last_pack', paused_from: null, remaining: 7, cigarettes_per_pack: 20, pack_price: 240,
  smoke_free_seconds: 0, best_smoke_free_seconds: 172800, attempt_number: 1,
  next_milestone_seconds: null, next_milestone_label: null, avoided_cigarettes: 0, saved_money: 0,
  risk: 'low', intervention: 'Выбери следующий маленький шаг.', reasons: 'Хочу легче начинать утро.',
  recent_triggers: [], preparation_steps: [], recovery_until: null, recovery_steps: [], target_quit_at: null,
};

async function installBearerSession(page: Page) {
  await page.addInitScript(() => {
    sessionStorage.setItem('kurilka-access-token', 'e2e-bearer-token');
    sessionStorage.setItem('kurilka-user-id', '42');
  });
}

test('bearer bootstrap completes 18+ onboarding and reaches the dashboard', async ({ page }) => {
  await installBearerSession(page);
  let onboarded = false;
  let onboardingPayload: Record<string, unknown> | null = null;
  await page.route('**/api/v1/bootstrap', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ age_confirmed: onboarded, consent_current: onboarded, onboarded, legal_documents_version: '2026-07-15', legal_documents_digest: '9f9298a64c2d8fd6b8552e055ba4834b1d32a037f0e60abd54decb6b78c6c30b' }) }));
  await page.route('**/api/v1/onboarding', async route => {
    onboardingPayload = await route.request().postDataJSON();
    onboarded = true;
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ phase: 'last_pack' }) });
  });
  await page.route('**/api/v1/dashboard', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(dashboard) }));

  await page.goto('/app');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Где начинается твой путь?');
  await page.getByRole('button', { name: /Продолжить/ }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Добавим только нужные числа');
  await page.getByLabel('Осталось сейчас').fill('7');
  await page.getByRole('button', { name: /Продолжить/ }).click();
  await page.getByLabel('Моя причина').fill('Хочу легче начинать утро.');
  await page.getByRole('button', { name: /Продолжить/ }).click();
  await expect(page.getByText('2026-07-15')).toBeVisible();
  await expect(page.getByText(/9f9298a64c2d…/)).toBeVisible();
  expect((await new AxeBuilder({ page }).include('.path-form-page').analyze()).violations).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  await page.locator('input[name="age"]').check();
  await page.locator('input[name="consent"]').check();
  await page.getByRole('button', { name: /Начать путь/ }).click();

  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Осталось 7');
  expect(onboardingPayload).toMatchObject({ start_mode: 'last_pack', remaining: 7, age_confirmed: true, consent: true });
  expect(await page.evaluate(() => localStorage.getItem('kurilka-onboarding-draft-v2'))).toBeNull();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test('document re-consent uses the dedicated endpoint and preserves the plan flow', async ({ page }) => {
  await installBearerSession(page);
  let consentCurrent = false;
  let consentPayload: Record<string, unknown> | null = null;
  let onboardingCalls = 0;
  await page.route('**/api/v1/bootstrap', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ age_confirmed: true, consent_current: consentCurrent, onboarded: true, legal_documents_version: '2026-07-15', legal_documents_digest: '9f9298a64c2d8fd6b8552e055ba4834b1d32a037f0e60abd54decb6b78c6c30b' }) }));
  await page.route('**/api/v1/consent', async route => {
    consentPayload = await route.request().postDataJSON();
    consentCurrent = true;
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ consent_version: '2026-07-15', consent_digest: '9f9298a64c2d8fd6b8552e055ba4834b1d32a037f0e60abd54decb6b78c6c30b', age_confirmed: true }) });
  });
  await page.route('**/api/v1/onboarding', route => { onboardingCalls += 1; return route.fulfill({ status: 500 }); });
  await page.route('**/api/v1/dashboard', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(dashboard) }));

  await page.goto('/app');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Подтверди условия');
  await expect(page.getByText('2026-07-15')).toBeVisible();
  await expect(page.getByText(/9f9298a64c2d…/)).toBeVisible();
  expect((await new AxeBuilder({ page }).include('.path-form-page').analyze()).violations).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  await page.locator('input[name="age"]').check();
  await page.locator('input[name="consent"]').check();
  await page.getByRole('button', { name: /Продолжить/ }).click();

  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Осталось 7');
  expect(consentPayload).toEqual({ age_confirmed: true, consent: true });
  expect(onboardingCalls).toBe(0);
});

test('a failed bootstrap recovers without clearing the bearer session', async ({ page }) => {
  await installBearerSession(page);
  let bootstrapCalls = 0;
  await page.route('**/api/v1/bootstrap', async route => {
    bootstrapCalls += 1;
    if (bootstrapCalls === 1) return route.abort('connectionrefused');
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ age_confirmed: true, consent_current: true, onboarded: true }) });
  });
  await page.route('**/api/v1/dashboard', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(dashboard) }));

  await page.goto('/app');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Сейчас нет сети');
  await page.getByRole('button', { name: 'Проверить соединение' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Осталось 7');
  expect(await page.evaluate(() => sessionStorage.getItem('kurilka-access-token'))).toBe('e2e-bearer-token');
});
