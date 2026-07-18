import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

const overview = {
  filters: { period: '30d', source: null }, users_total: 100,
  users_by_acquisition_source: { direct: 60, newsletter: 40 }, activation: { onboarded: 64, rate: 0.64 },
  funnel: { started: 100, onboarded: 64, first_action_24h: 30, first_action_rate: 0.4688 },
  retention: { d1: { eligible: 50, retained: 22, rate: 0.44 }, d7: { eligible: 40, retained: 10, rate: 0.25 }, d14: { eligible: 20, retained: 3, rate: 0.15 } },
  notification_health: { muted: 9, preferences_total: 60, mute_rate: 0.15, delivery_failures_last_24h: 1, delivery_failure_rate: 0.01 },
  client_health: { sessions: 1000, crashed: 3, crash_free_rate: 0.997 },
  plans_by_phase: { preparation: 20, last_pack: 18, quit: 26 }, events_last_24h: 42,
  deliveries_last_24h: { sent: 20, failed: 1 }, outbox_by_status: { pending: 2, processed: 50 },
  open_feedback: 1, content_review_status: 'pending_external_review', content_version: 'v1-draft', content_digest: '0123456789abcdef'.repeat(4), risk_engine_version: 'v1',
};

test('staff dashboard filters safe metrics and triages feedback', async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.setItem('kurilka-access-token', 'staff-e2e-token');
    sessionStorage.setItem('kurilka-user-id', '7');
  });
  const overviewQueries: URLSearchParams[] = [];
  let resolved = false;
  let patchPayload: Record<string, unknown> | null = null;
  await page.route('**/api/v1/admin/overview?*', route => {
    const query = new URL(route.request().url()).searchParams;
    overviewQueries.push(query);
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...overview, filters: { period: query.get('period'), source: query.get('source') } }) });
  });
  await page.route('**/api/v1/admin/feedback?*', route => {
    const status = new URL(route.request().url()).searchParams.get('status');
    const item = { id: 12, category: 'idea', body: 'Сделать объяснение следующего шага короче.', status: resolved ? 'resolved' : 'open', created_at: '2026-07-14T09:00:00Z', resolved_at: resolved ? '2026-07-14T10:00:00Z' : null };
    const items = status === item.status ? [item] : [];
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(items) });
  });
  await page.route('**/api/v1/admin/feedback/12', async route => {
    patchPayload = await route.request().postDataJSON();
    resolved = true;
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ id: 12, status: 'resolved' }) });
  });

  await page.goto('/staff');
  await expect(page.getByRole('heading', { name: 'Пилот', level: 1 })).toBeVisible();
  await expect(page.getByText('100', { exact: true })).toBeVisible();
  await expect(page.getByText(/полностью завершённые окна/)).toBeVisible();
  await expect(page.getByText(/sent \+ failed/)).toBeVisible();
  await expect(page.getByText(/Crash-free: 99.70%/)).toBeVisible();
  await expect(page.getByText('0123456789ab')).toBeVisible();
  await expect(page.getByText('Сделать объяснение следующего шага короче.')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  expect((await new AxeBuilder({ page }).include('.path-staff-page').analyze()).violations).toEqual([]);

  await page.getByLabel('Период').selectOption('7d');
  await page.getByLabel('Источник').selectOption('newsletter');
  await expect.poll(() => overviewQueries.some(query => query.get('period') === '7d' && query.get('source') === 'newsletter')).toBe(true);

  await page.getByRole('button', { name: 'Закрыть обращение' }).click();
  await expect.poll(() => patchPayload).toEqual({ status: 'resolved' });
  await expect(page.getByText('В этой очереди сообщений нет.')).toBeVisible();
  await page.getByRole('button', { name: 'Закрытые' }).click();
  await expect(page.getByText('Сделать объяснение следующего шага короче.')).toBeVisible();
  await expect(page.getByText(/Telegram ID и пользовательских причин/)).toBeVisible();
});

test('staff access denial is explicit and never renders operational data', async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.setItem('kurilka-access-token', 'non-staff-e2e-token');
    sessionStorage.setItem('kurilka-user-id', '8');
  });
  const denied = { status: 403, contentType: 'application/json', body: JSON.stringify({ error: { code: 'staff_forbidden', message: 'Forbidden', request_id: 'staff-403' } }) };
  await page.route('**/api/v1/admin/overview?*', route => route.fulfill(denied));
  await page.route('**/api/v1/admin/feedback?*', route => route.fulfill(denied));

  await page.goto('/staff');
  await expect(page.getByRole('status')).toContainText('не добавлен в ADMIN_TELEGRAM_IDS');
  await expect(page.locator('.metrics')).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Операционный статус' })).toHaveCount(0);
  expect((await new AxeBuilder({ page }).include('.path-staff-page').analyze()).violations).toEqual([]);
});

test('staff metrics distinguish missing denominators from a measured zero', async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.setItem('kurilka-access-token', 'staff-empty-e2e-token');
    sessionStorage.setItem('kurilka-user-id', '9');
  });
  const emptyOverview = {
    ...overview,
    users_total: 0,
    users_by_acquisition_source: {},
    activation: { onboarded: 0, rate: 0 },
    funnel: { started: 0, onboarded: 0, first_action_24h: 0, first_action_rate: 0 },
    retention: { d1: { eligible: 0, retained: 0, rate: 0 }, d7: { eligible: 0, retained: 0, rate: 0 }, d14: { eligible: 0, retained: 0, rate: 0 } },
    notification_health: { muted: 0, preferences_total: 0, mute_rate: 0, delivery_failures_last_24h: 0, delivery_failure_rate: 0 },
    client_health: { sessions: 0, crashed: 0, crash_free_rate: 0 },
    plans_by_phase: {}, events_last_24h: 0, deliveries_last_24h: {}, outbox_by_status: {}, open_feedback: 0,
  };
  await page.route('**/api/v1/admin/overview?*', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(emptyOverview) }));
  await page.route('**/api/v1/admin/feedback?*', route => route.fulfill({ status: 200, contentType: 'application/json', body: '[]' }));

  await page.goto('/staff');
  await expect(page.getByText(/Crash-free: нет данных/)).toBeVisible();
  await expect(page.getByText(/Первое действие ≤24 ч: 0\/0 \(нет данных\)/)).toBeVisible();
  await expect(page.getByText(/D1: нет полного окна/)).toBeVisible();
  await expect(page.getByText(/Delivery failures за 24 часа: 0 \(нет завершённых попыток\)/)).toBeVisible();
  expect((await new AxeBuilder({ page }).include('.path-staff-page').analyze()).violations).toEqual([]);
});
