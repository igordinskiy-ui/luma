import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

const dashboard = {
  phase: 'last_pack', paused_from: null, remaining: 7, cigarettes_per_pack: 20, pack_price: 240,
  smoke_free_seconds: 0, best_smoke_free_seconds: 172800, attempt_number: 1,
  next_milestone_seconds: null, next_milestone_label: null, avoided_cigarettes: 0, saved_money: 0,
  risk: 'low', intervention: 'Выбери следующий маленький шаг.', reasons: 'Хочу легче начинать утро.',
  recent_triggers: [], preparation_steps: [], recovery_until: null, recovery_steps: [], target_quit_at: null,
};

test('OIDC callback survives a network interruption and returns to the journal', async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.setItem('kurilka-oidc-state', 'client-state-1234567890123456');
    sessionStorage.setItem('kurilka-oidc-return', '/journal');
  });
  let completionCalls = 0;
  await page.route('**/api/v1/auth/oidc/complete', async route => {
    completionCalls += 1;
    if (completionCalls === 1) return route.abort('connectionrefused');
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ access_token: 'recovered-token', token_type: 'bearer', user_id: 42 }) });
  });
  await page.route('**/api/v1/bootstrap', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ age_confirmed: true, consent_current: true, onboarded: true }) }));
  await page.route('**/api/v1/dashboard', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(dashboard) }));
  await page.route('**/api/v1/journal**', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [], next_cursor: null, summary: { total: 0, cravings: 0, coping_completed: 0, relapses: 0, sufficient_data: false, top_trigger: null } }) }));

  await page.goto('/app#oidc_code=completion-code-1234567890123456&state=client-state-1234567890123456');
  await expect(page.getByRole('heading', { name: 'Связь прервалась' })).toBeVisible();
  expect(page.url()).not.toContain('oidc_code');
  expect((await new AxeBuilder({ page }).include('.path-state-page').analyze()).violations).toEqual([]);

  await page.getByRole('button', { name: 'Повторить завершение' }).click();
  await expect(page).toHaveURL(/\/journal$/);
  await expect(page.getByRole('heading', { name: 'Журнал' })).toBeVisible();
  expect(completionCalls).toBe(2);
  expect(await page.evaluate(() => sessionStorage.getItem('kurilka-access-token'))).toBe('recovered-token');
  expect(await page.evaluate(() => sessionStorage.getItem('kurilka-oidc-pending'))).toBeNull();
});

test('expired bearer offers a fresh Telegram login and preserves the settings return path', async ({ page }) => {
  await page.addInitScript(() => {
    if (sessionStorage.getItem('e2e-auth-seeded')) return;
    sessionStorage.setItem('e2e-auth-seeded', '1');
    sessionStorage.setItem('kurilka-access-token', 'expired-token');
    sessionStorage.setItem('kurilka-user-id', '42');
  });
  await page.route('**/api/v1/bootstrap', route => route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ error: { code: 'invalid_session', message: 'Session expired', request_id: 'auth-e2e' } }) }));
  let startUrl = '';
  await page.route('**/api/v1/auth/oidc/start?**', async route => {
    startUrl = route.request().url();
    await route.fulfill({ status: 200, contentType: 'text/html', body: '<p>Telegram authorization</p>' });
  });

  await page.goto('/settings');
  await expect(page.getByRole('heading', { name: 'Нужно войти снова' })).toBeVisible();
  await page.getByRole('button', { name: 'Войти через Telegram' }).click();
  await expect(page.getByText('Telegram authorization')).toBeVisible();
  expect(startUrl).toContain('/api/v1/auth/oidc/start?client_state=');
  expect(await page.evaluate(() => sessionStorage.getItem('kurilka-oidc-return'))).toBe('/settings');
  expect(await page.evaluate(() => sessionStorage.getItem('kurilka-access-token'))).toBeNull();
});
