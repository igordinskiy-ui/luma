import AxeBuilder from '@axe-core/playwright';
import { expect, Page, test } from '@playwright/test';

const dashboard = {
  phase: 'last_pack', paused_from: null, remaining: 7, cigarettes_per_pack: 20, pack_price: 240,
  smoke_free_seconds: 0, best_smoke_free_seconds: 0, attempt_number: 1,
  next_milestone_seconds: null, next_milestone_label: null, avoided_cigarettes: 0, saved_money: 0,
  risk: 'low', intervention: 'Следующий шаг.', reasons: 'Моя причина.', recent_triggers: [],
  preparation_steps: [], recovery_until: null, recovery_steps: [], target_quit_at: null,
};

async function mockSettingsApi(page: Page, state: { deleted: boolean; logoutCalls: number; pushDeletes: number }) {
  await page.addInitScript(() => {
    if (!sessionStorage.getItem('settings-e2e-seeded')) {
      sessionStorage.setItem('settings-e2e-seeded', '1');
      sessionStorage.setItem('kurilka-access-token', 'settings-e2e-token');
      sessionStorage.setItem('kurilka-user-id', '42');
      sessionStorage.setItem('kurilka-client-session-id', '44444444-4444-4444-8444-444444444444');
      sessionStorage.setItem('kurilka-client-crash-reported', '1');
    }
  });
  await page.route('**/api/v1/bootstrap', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(state.deleted ? { age_confirmed: false, consent_current: false, onboarded: false } : { age_confirmed: true, consent_current: true, onboarded: true }) }));
  await page.route('**/api/v1/dashboard', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(dashboard) }));
  await page.route('**/api/v1/notification-preferences', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ enabled: false, max_daily: 3, quiet_start: 22, quiet_end: 9 }) }));
  await page.route('**/api/v1/notification-status', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ enabled: false, can_send_now: false, telegram: 'available', web_push: 'not_subscribed', subscriptions: 0 }) }));
  await page.route('**/api/v1/quit-plan', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ phase: 'last_pack', paused_from: null, remaining: 7, cigarettes_per_pack: 20, pack_price: 240, reasons: 'Моя причина.', quit_started_at: null, target_quit_at: null, recovery_until: null }) }));
  await page.route('**/api/v1/privacy-export', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ account: { id: 42 }, quit_plan: { phase: 'last_pack' }, events: [] }) }));
  await page.route('**/api/v1/push-subscription', route => { if (route.request().method() === 'DELETE') state.pushDeletes += 1; return route.fulfill({ status: 204 }); });
  await page.route('**/api/v1/logout', route => { state.logoutCalls += 1; return route.fulfill({ status: 204 }); });
  await page.route('**/api/v1/account', route => { state.deleted = true; return route.fulfill({ status: 204 }); });
}

test('settings exports data and revokes the device session on logout', async ({ page }) => {
  const state = { deleted: false, logoutCalls: 0, pushDeletes: 0 };
  await mockSettingsApi(page, state);
  await page.goto('/settings');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Настройки');
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: /Экспортировать данные/ }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('kurilka-data.json');
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);

  await page.getByRole('button', { name: /Выйти со всех устройств/ }).click();
  await expect(page).toHaveURL(/\/$/);
  expect(state.logoutCalls).toBe(1);
  expect(state.pushDeletes).toBe(1);
  expect(await page.evaluate(() => sessionStorage.getItem('kurilka-access-token'))).toBeNull();
  expect(await page.evaluate(() => sessionStorage.getItem('kurilka-client-session-id'))).toBeNull();
  expect(await page.evaluate(() => sessionStorage.getItem('kurilka-client-crash-reported'))).toBeNull();
});

test('account deletion requires typed confirmation and a returning user sees onboarding', async ({ page }) => {
  const state = { deleted: false, logoutCalls: 0, pushDeletes: 0 };
  await mockSettingsApi(page, state);
  await page.goto('/settings');
  await page.getByRole('button', { name: 'Удалить аккаунт', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Удалить весь путь?' });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Удалить аккаунт безвозвратно' })).toBeDisabled();
  expect((await new AxeBuilder({ page }).include('.path-support-sheet').analyze()).violations).toEqual([]);
  await dialog.getByLabel('Подтверждение').fill('УДАЛИТЬ');
  await dialog.getByRole('button', { name: 'Удалить аккаунт безвозвратно' }).click();
  await expect(page).toHaveURL(/\/$/);
  expect(state.deleted).toBe(true);
  expect(await page.evaluate(() => sessionStorage.getItem('kurilka-client-session-id'))).toBeNull();
  expect(await page.evaluate(() => sessionStorage.getItem('kurilka-client-crash-reported'))).toBeNull();

  await page.evaluate(() => {
    sessionStorage.setItem('kurilka-access-token', 'returning-e2e-token');
    sessionStorage.setItem('kurilka-user-id', '42');
  });
  await page.goto('/app');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Где начинается твой путь?');
});

test('notification opt-in saves limits before exposing a quiet-hours test result', async ({ page }) => {
  const state = { deleted: false, logoutCalls: 0, pushDeletes: 0 };
  await mockSettingsApi(page, state);
  let saved: Record<string, unknown> | null = null;
  await page.unroute('**/api/v1/notification-preferences');
  await page.unroute('**/api/v1/notification-status');
  await page.route('**/api/v1/notification-preferences', async route => {
    if (route.request().method() === 'PUT') saved = await route.request().postDataJSON();
    const payload = saved || { enabled: false, max_daily: 3, quiet_start: 22, quiet_end: 9 };
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) });
  });
  await page.route('**/api/v1/notification-status', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ enabled: Boolean(saved?.enabled), can_send_now: false, telegram: 'available', web_push: 'not_subscribed', subscriptions: 0 }) }));
  await page.route('**/api/v1/notifications/test', route => route.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify({ error: { code: 'notification_unavailable', message: 'Quiet hours', request_id: 'notification-1' } }) }));

  await page.goto('/settings');
  const notificationOptIn = page.getByRole('checkbox', { name: 'Разрешить поддерживающие сообщения' });
  await page.locator('label.path-switch').click();
  await expect(notificationOptIn).toBeChecked();
  await page.getByLabel('Максимум сообщений в день').selectOption('2');
  await page.getByLabel('Не беспокоить с').fill('23');
  await page.getByLabel('до', { exact: true }).fill('8');
  await page.getByRole('button', { name: /Сохранить расписание/ }).click();
  await expect(page.getByRole('status')).toContainText('Настройки сохранены.');
  expect(saved).toEqual({ enabled: true, max_daily: 2, quiet_start: 23, quiet_end: 8 });

  await page.getByRole('button', { name: 'Отправить тест' }).click();
  await expect(page.getByRole('status')).toContainText('проверь opt-in, тихие часы и подключённый канал');

  await page.locator('label.path-switch').click();
  await page.getByRole('button', { name: /Сохранить расписание/ }).click();
  await expect(page.getByRole('status')).toContainText('Рассылка выключена — новые сообщения не планируются');
  await expect(page.getByRole('button', { name: 'Отправить тест' })).toBeDisabled();
  expect(saved).toEqual({ enabled: false, max_daily: 2, quiet_start: 23, quiet_end: 8 });
  expect((await new AxeBuilder({ page }).include('.path-settings-page').analyze()).violations).toEqual([]);
});

test('plan editing saves preparation details and preserves the draft after a failed retry', async ({ page }) => {
  const state = { deleted: false, logoutCalls: 0, pushDeletes: 0 };
  await mockSettingsApi(page, state);
  await page.unroute('**/api/v1/quit-plan');
  const saved: Record<string, unknown>[] = [];
  let rejectSave = false;
  await page.route('**/api/v1/quit-plan', async route => {
    if (route.request().method() === 'GET') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ phase: 'preparation', paused_from: null, remaining: 20, cigarettes_per_pack: 20, pack_price: 240, reasons: 'Старый текст', quit_started_at: null, target_quit_at: '2026-07-30T09:00:00Z', recovery_until: null }) });
    }
    const payload = await route.request().postDataJSON();
    saved.push(payload);
    if (rejectSave) return route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ error: { code: 'save_failed', message: 'Позже', request_id: 'plan-save-1' } }) });
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ phase: 'preparation', remaining: 20 }) });
  });

  await page.goto('/settings');
  const reason = page.getByLabel('Почему это важно');
  await expect(reason).toHaveValue('Старый текст');
  await reason.fill('Хочу спокойно встречать утро');
  await page.getByLabel('Сигарет в пачке').fill('25');
  await page.getByLabel('Цена пачки, ₽').fill('315.50');
  await page.getByLabel('Дата старта').fill('2020-01-01T09:30');
  await page.getByRole('button', { name: /Сохранить план/ }).click();
  await expect(page.getByRole('alert')).toContainText('Выбери дату и время в будущем');
  await expect(reason).toHaveValue('Хочу спокойно встречать утро');
  expect(saved).toHaveLength(0);

  const future = await page.evaluate(() => {
    const date = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000);
    date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
    const fieldValue = date.toISOString().slice(0, 16);
    return { fieldValue, expectedIso: new Date(fieldValue).toISOString() };
  });
  await page.getByLabel('Дата старта').fill(future.fieldValue);
  await page.getByRole('button', { name: /Сохранить план/ }).click();
  await expect(page.getByRole('status')).toContainText('История осталась на месте');
  expect(saved[0]).toMatchObject({ reasons: 'Хочу спокойно встречать утро', cigarettes_per_pack: 25, pack_price: 315.5 });
  expect(saved[0].target_quit_at).toBe(future.expectedIso);

  rejectSave = true;
  await reason.fill('Новый текст, который нельзя потерять');
  await page.getByRole('button', { name: /Сохранить план/ }).click();
  await expect(page.getByRole('alert')).toContainText('Введённые данные остались на экране');
  await expect(reason).toHaveValue('Новый текст, который нельзя потерять');
  expect((await new AxeBuilder({ page }).include('.path-settings-page').analyze()).violations).toEqual([]);
});

test('web push lifecycle subscribes, verifies the channel and removes the device subscription', async ({ page }) => {
  const state = { deleted: false, logoutCalls: 0, pushDeletes: 0 };
  await mockSettingsApi(page, state);
  await page.addInitScript(() => {
    Object.defineProperty(window, 'Notification', { configurable: true, value: { permission: 'default', requestPermission: async () => 'granted' } });
    const testWindow = window as typeof window & { __pushSubscribed?: boolean; __pushUnsubscribed?: boolean };
    const subscription = {
      endpoint: 'https://fcm.googleapis.com/e2e-device',
      toJSON: () => ({ keys: { p256dh: 'p256dh-e2e', auth: 'auth-e2e' } }),
      unsubscribe: async () => { testWindow.__pushUnsubscribed = true; return true; },
    };
    const pushManager = {
      subscribe: async () => { testWindow.__pushSubscribed = true; return subscription; },
      getSubscription: async () => subscription,
    };
    Object.defineProperty(ServiceWorkerRegistration.prototype, 'pushManager', { configurable: true, get: () => pushManager });
  });
  await page.unroute('**/api/v1/notification-status');
  await page.unroute('**/api/v1/push-subscription');
  let subscribed = false;
  let savedPush: Record<string, unknown> | null = null;
  let deleted = 0;
  await page.route('**/api/v1/push-public-key', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ public_key: 'AQAB' }) }));
  await page.route('**/api/v1/notification-status', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ enabled: false, can_send_now: false, telegram: 'available', web_push: subscribed ? 'subscribed' : 'not_subscribed', subscriptions: subscribed ? 1 : 0 }) }));
  await page.route('**/api/v1/push-subscription', async route => {
    if (route.request().method() === 'PUT') {
      savedPush = await route.request().postDataJSON();
      subscribed = true;
    } else {
      subscribed = false;
      deleted += 1;
    }
    return route.fulfill({ status: 204 });
  });

  await page.goto('/settings');
  await page.getByRole('button', { name: 'Подключить web push' }).click();
  await expect(page.getByRole('status')).toContainText('Web push подключены');
  await expect(page.getByText('Подключён', { exact: true })).toBeVisible();
  expect(savedPush).toEqual({ endpoint: 'https://fcm.googleapis.com/e2e-device', p256dh: 'p256dh-e2e', auth: 'auth-e2e' });
  expect(await page.evaluate(() => (window as typeof window & { __pushSubscribed?: boolean }).__pushSubscribed)).toBe(true);

  await page.getByRole('button', { name: 'Отключить web push' }).click();
  await expect(page.getByRole('status')).toContainText('подписка удалена');
  await expect(page.getByText('Не подключён', { exact: true })).toBeVisible();
  expect(deleted).toBe(1);
  expect(await page.evaluate(() => (window as typeof window & { __pushUnsubscribed?: boolean }).__pushUnsubscribed)).toBe(true);
});

test('a push endpoint owned by another profile is locally reset for a safe retry', async ({ page }) => {
  const state = { deleted: false, logoutCalls: 0, pushDeletes: 0 };
  await mockSettingsApi(page, state);
  await page.addInitScript(() => {
    Object.defineProperty(window, 'Notification', { configurable: true, value: { requestPermission: async () => 'granted' } });
    const subscription = {
      endpoint: 'https://fcm.googleapis.com/previous-profile',
      toJSON: () => ({ keys: { p256dh: 'p256dh-conflict', auth: 'auth-conflict' } }),
      unsubscribe: async () => { (window as typeof window & { __conflictUnsubscribed?: boolean }).__conflictUnsubscribed = true; return true; },
    };
    Object.defineProperty(ServiceWorkerRegistration.prototype, 'pushManager', { configurable: true, get: () => ({ subscribe: async () => subscription, getSubscription: async () => subscription }) });
  });
  await page.unroute('**/api/v1/push-subscription');
  await page.route('**/api/v1/push-public-key', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ public_key: 'AQAB' }) }));
  await page.route('**/api/v1/push-subscription', route => route.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify({ error: { code: 'http_409', message: 'Owned by another account', request_id: 'push-owner-1' } }) }));

  await page.goto('/settings');
  await page.getByRole('button', { name: 'Подключить web push' }).click();
  await expect(page.getByRole('status')).toContainText('связана с другим профилем и очищена');
  expect(await page.evaluate(() => (window as typeof window & { __conflictUnsubscribed?: boolean }).__conflictUnsubscribed)).toBe(true);
  expect((await new AxeBuilder({ page }).include('.path-settings-page').analyze()).violations).toEqual([]);
});
