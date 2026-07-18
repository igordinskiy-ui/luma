import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

const dashboard = {
  phase: 'quit', paused_from: null, remaining: 0, cigarettes_per_pack: 20, pack_price: 240,
  smoke_free_seconds: 86400, best_smoke_free_seconds: 172800, attempt_number: 2,
  next_milestone_seconds: 259200, next_milestone_label: '3 дня', avoided_cigarettes: 16, saved_money: 192,
  risk: 'low', intervention: 'Следующий шаг.', reasons: 'Хочу легче начинать утро.', recent_triggers: [],
  preparation_steps: [], recovery_until: null, recovery_steps: [], target_quit_at: null,
};

const craving = {
  id: 'event:1', source: 'event', type: 'craving', created_at: '2026-07-14T09:15:00Z',
  trigger: 'coffee', intensity_before: 4, note: 'Заметил тягу и остановился.', editable_until: '2099-07-14T09:30:00Z',
};

const coping = {
  id: 'coping:7', source: 'coping', type: 'coping', created_at: '2026-07-14T09:17:00Z',
  trigger: 'coffee', intensity_before: 7, intensity_after: 3, technique: 'water', status: 'completed', outcome: 'helped', note: '',
};

const smoked = {
  id: 'event:9', source: 'event', type: 'smoked', created_at: '2026-07-14T09:18:00Z',
  trigger: 'habit', intensity_before: 3, note: '', editable_until: '2099-07-14T09:33:00Z',
};

async function mockAuthenticatedApp(page: Page) {
  await page.addInitScript(() => {
    sessionStorage.setItem('kurilka-access-token', 'journal-e2e-token');
    sessionStorage.setItem('kurilka-user-id', '42');
  });
  await page.route('**/api/v1/bootstrap', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ age_confirmed: true, consent_current: true, onboarded: true }) }));
  await page.route('**/api/v1/dashboard', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(dashboard) }));
}

test('journal renders an RFC 3339 instant in the device timezone', async ({ browser }) => {
  const context = await browser.newContext({ timezoneId: 'Europe/Moscow' });
  const page = await context.newPage();
  await mockAuthenticatedApp(page);
  await page.route('**/api/v1/journal?*', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ items: [craving], next_cursor: null, summary: { total: 1, cravings: 1, coping_completed: 0, relapses: 0, sufficient_data: false, top_trigger: null } }),
  }));

  await page.goto('/journal');
  await expect(page.getByText('Время показано по часовому поясу этого устройства.', { exact: false })).toBeVisible();
  await expect(page.locator('time[datetime="2026-07-14T09:15:00Z"]')).toHaveText('12:15');
  await context.close();
});

test('journal paginates without duplicates and applies server filters', async ({ page }) => {
  await mockAuthenticatedApp(page);
  const queries: URLSearchParams[] = [];
  await page.route('**/api/v1/journal?*', route => {
    const query = new URL(route.request().url()).searchParams;
    queries.push(query);
    const filtered = query.get('type') === 'craving';
    const secondPage = query.get('cursor') === 'cursor-2';
    const payload = filtered
      ? { items: [craving], next_cursor: null, summary: { total: 1, cravings: 1, coping_completed: 0, relapses: 0, sufficient_data: false, top_trigger: 'coffee' } }
      : secondPage
        ? { items: [craving, { ...coping, id: 'coping:8', technique: 'breathing', created_at: '2026-07-13T08:00:00Z' }], next_cursor: null, summary: { total: 3, cravings: 1, coping_completed: 2, relapses: 0, sufficient_data: true, top_trigger: 'coffee' } }
        : { items: [craving, coping], next_cursor: 'cursor-2', summary: { total: 3, cravings: 1, coping_completed: 2, relapses: 0, sufficient_data: true, top_trigger: 'coffee' } };
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) });
  });

  await page.goto('/journal');
  await expect(page.getByRole('heading', { name: 'Журнал', level: 1 })).toBeVisible();
  await expect(page.getByRole('listitem')).toHaveCount(2);
  expect((await new AxeBuilder({ page }).include('.path-journal-page').analyze()).violations).toEqual([]);

  await page.getByRole('button', { name: 'Показать ещё' }).click();
  await expect(page.getByRole('listitem')).toHaveCount(3);
  expect(queries.some(query => query.get('cursor') === 'cursor-2')).toBe(true);

  await page.getByRole('button', { name: 'Тяга', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Тяга', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByRole('listitem')).toHaveCount(1);
  expect(queries.some(query => query.get('type') === 'craving' && query.get('period') === '7d')).toBe(true);
  await expect(page.getByText('Пока данных мало для честного вывода.', { exact: false })).toBeVisible();
});

test('journal keeps a clear retry and empty-state path', async ({ page }) => {
  await mockAuthenticatedApp(page);
  let attempts = 0;
  await page.route('**/api/v1/journal?*', route => {
    attempts += 1;
    if (attempts === 1) return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ error: { code: 'maintenance', message: 'Позже', request_id: 'journal-1' } }) });
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [], next_cursor: null, summary: { total: 0, cravings: 0, coping_completed: 0, relapses: 0, sufficient_data: false, top_trigger: null } }) });
  });

  await page.goto('/journal');
  await expect(page.getByRole('alert')).toContainText('Не удалось загрузить журнал');
  await page.getByRole('button', { name: 'Повторить' }).click();
  await expect(page.getByRole('heading', { name: 'Здесь пока тихо' })).toBeVisible();
  await expect(page.getByRole('button', { name: /Зафиксировать тягу/ })).toBeVisible();
  expect((await new AxeBuilder({ page }).include('.path-journal-page').analyze()).violations).toEqual([]);
});

test('journal explains a correction-window race without losing the entry', async ({ page }) => {
  await mockAuthenticatedApp(page);
  await page.route('**/api/v1/journal?*', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [craving], next_cursor: null, summary: { total: 1, cravings: 1, coping_completed: 0, relapses: 0, sufficient_data: false, top_trigger: 'coffee' } }) }));
  await page.route('**/api/v1/events/1', route => route.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify({ error: { code: 'edit_window_expired', message: 'Окно исправления закрыто', request_id: 'journal-edit-1' } }) }));

  await page.goto('/journal');
  await page.getByRole('button', { name: 'Исправить' }).click();
  const dialog = page.getByRole('dialog', { name: 'Исправить событие' });
  await expect(dialog).toBeVisible();
  expect((await new AxeBuilder({ page }).include('.path-edit-dialog').analyze()).violations).toEqual([]);
  await dialog.getByRole('button', { name: /Сохранить исправление/ }).click();
  await expect(dialog.getByRole('alert')).toContainText('окно исправления уже закрылось');
  await dialog.getByRole('button', { name: 'Закрыть' }).click();
  await expect(page.getByText('Заметил тягу и остановился.')).toBeVisible();
});

test('journal removes an accidental cigarette only after a clear confirmation', async ({ page }) => {
  await mockAuthenticatedApp(page);
  let deleted = false;
  await page.route('**/api/v1/journal?*', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(deleted
    ? { items: [], next_cursor: null, summary: { total: 0, cravings: 0, coping_completed: 0, relapses: 0, sufficient_data: false, top_trigger: null } }
    : { items: [smoked], next_cursor: null, summary: { total: 1, cravings: 0, coping_completed: 0, relapses: 0, sufficient_data: false, top_trigger: 'habit' } }) }));
  await page.route('**/api/v1/events/9', route => {
    expect(route.request().method()).toBe('DELETE');
    deleted = true;
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'deleted', phase: 'last_pack', remaining: 1 }) });
  });

  await page.goto('/journal');
  await page.getByRole('button', { name: 'Исправить' }).click();
  await page.getByRole('button', { name: 'Убрать ошибочную отметку' }).click();
  const dialog = page.getByRole('dialog', { name: 'Убрать ошибочную отметку?' });
  await expect(dialog).toContainText('счётчик сигарет и этап пути вернутся');
  await expect(dialog.getByRole('button', { name: 'Да, убрать отметку' })).toBeFocused();
  expect((await new AxeBuilder({ page }).include('.path-edit-dialog').analyze()).violations).toEqual([]);
  await dialog.getByRole('button', { name: 'Да, убрать отметку' }).click();
  await expect(page.getByRole('heading', { name: 'Здесь пока тихо' })).toBeVisible();
  expect(deleted).toBe(true);
});
