import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

const dashboard = {
  phase: 'quit', paused_from: null, remaining: 0, cigarettes_per_pack: 20, pack_price: 240,
  smoke_free_seconds: 86400, best_smoke_free_seconds: 172800, attempt_number: 2,
  next_milestone_seconds: 259200, next_milestone_label: '3 дня', avoided_cigarettes: 16, saved_money: 192,
  risk: 'low', intervention: 'Следующий шаг.', reasons: 'Хочу легче начинать утро.', recent_triggers: [],
  preparation_steps: [], recovery_until: null, recovery_steps: [], target_quit_at: null,
};

test('coping lifecycle survives a mid-session network loss and replays in order', async ({ page, context }) => {
  await page.addInitScript(() => {
    sessionStorage.setItem('kurilka-access-token', 'coping-e2e-token');
    sessionStorage.setItem('kurilka-user-id', '42');
  });
  const starts: Record<string, unknown>[] = [];
  const patches: Record<string, unknown>[] = [];
  let networkOnline = true;
  await page.route('**/api/v1/bootstrap', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ age_confirmed: true, consent_current: true, onboarded: true }) }));
  await page.route('**/api/v1/dashboard', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(dashboard) }));
  await page.route('**/api/v1/coping-techniques', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ content_version: 'v1', techniques: [
    { id: 'breathing', title: 'Медленный выдох', duration_seconds: 300, instruction: 'Делай выдох немного длиннее вдоха.' },
    { id: 'water', title: 'Стакан воды', duration_seconds: 180, instruction: 'Пей небольшими глотками.' },
  ] }) }));
  await page.route('**/api/v1/coping-sessions', async route => {
    if (!networkOnline) return route.abort('internetdisconnected');
    const payload = await route.request().postDataJSON();
    starts.push(payload);
    await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify({ ...payload, id: 91, content_version: 'v1', status: 'active', started_at: '2026-07-14T00:00:00Z', updated_at: '2026-07-14T00:00:00Z' }) });
  });
  await page.route('**/api/v1/coping-sessions/91', async route => {
    if (!networkOnline) return route.abort('internetdisconnected');
    const payload = await route.request().postDataJSON();
    patches.push(payload);
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...starts[0], ...payload, id: 91, content_version: 'v1', status: payload.status || 'active', started_at: '2026-07-14T00:00:00Z', updated_at: '2026-07-14T00:00:00Z' }) });
  });

  await page.goto('/app');
  await page.getByRole('button', { name: /Мне сейчас тяжело/ }).click();
  await page.getByRole('button', { name: 'Кофе' }).click();
  await page.getByRole('button', { name: /Подобрать действие/ }).click();
  await page.getByRole('button', { name: /Стакан воды/ }).click();
  expect(starts).toHaveLength(1);

  networkOnline = false;
  await context.setOffline(true);
  try {
    await page.getByRole('button', { name: /Начать · 3 мин/ }).click();
    await expect(page.getByRole('heading', { name: 'Сейчас — только этот шаг' })).toBeVisible();
    expect((await new AxeBuilder({ page }).include('.path-support-sheet').analyze()).violations).toEqual([]);
    await page.getByRole('button', { name: 'Пауза', exact: true }).click();
    await page.getByRole('button', { name: 'Сменить способ' }).click();
    await page.getByRole('button', { name: /Медленный выдох/ }).click();
    await page.getByRole('button', { name: /Начать · 5 мин/ }).click();
    await page.getByRole('button', { name: /Оценить тягу снова/ }).click();
    await page.getByRole('button', { name: 'Стало легче' }).click();
    await page.getByRole('button', { name: /Сохранить результат/ }).click();
    await expect(page.getByText('Сессия сохранена на устройстве и синхронизируется позже.')).toBeVisible();
    const queued = await page.evaluate(() => localStorage.getItem('kurilka-coping-queue:42') || '');
    expect(queued).toContain('"technique":"water"');
    expect(queued).toContain('"status":"paused"');
    expect(queued).toContain('"technique":"breathing"');
    expect(queued).toContain('"status":"completed"');
  } finally {
    networkOnline = true;
    await context.setOffline(false);
  }

  await page.evaluate(() => window.dispatchEvent(new Event('online')));
  await expect.poll(() => starts.length).toBe(2);
  await expect.poll(() => patches.length).toBe(4);
  expect(patches).toEqual([
    { technique: 'water' },
    { status: 'paused' },
    { technique: 'breathing' },
    { status: 'completed', intensity_after: 3, outcome: 'helped' },
  ]);
  expect(await page.evaluate(() => localStorage.getItem('kurilka-coping-queue:42'))).toBe('[]');
});
