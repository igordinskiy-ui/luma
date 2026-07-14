import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import type { Dashboard } from '../src/api';

const initialDashboard: Dashboard = {
  phase: 'last_pack', paused_from: null, remaining: 7, cigarettes_per_pack: 20, pack_price: 240,
  smoke_free_seconds: 0, best_smoke_free_seconds: 86400, attempt_number: 0,
  next_milestone_seconds: null, next_milestone_label: null, avoided_cigarettes: 0, saved_money: 0,
  risk: 'low', intervention: 'Следующий честный шаг.', reasons: 'Хочу легче начинать утро.', recent_triggers: [],
  preparation_steps: [], recovery_until: null, recovery_steps: [], target_quit_at: null,
};

test('journey moves from last pack through pause, resume and recovery without losing history', async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.setItem('kurilka-access-token', 'journey-e2e-token');
    sessionStorage.setItem('kurilka-user-id', '42');
  });
  const dashboard: Dashboard = { ...initialDashboard };
  const transitions: Record<string, unknown>[] = [];
  const events: Record<string, unknown>[] = [];
  await page.route('**/api/v1/bootstrap', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ age_confirmed: true, consent_current: true, onboarded: true }) }));
  await page.route('**/api/v1/dashboard', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(dashboard) }));
  await page.route('**/api/v1/quit-plan', async route => {
    const payload = await route.request().postDataJSON();
    transitions.push(payload);
    const next = payload.phase as 'last_pack' | 'quit' | 'paused';
    if (next === 'paused') {
      dashboard.paused_from = dashboard.phase as 'last_pack' | 'quit';
      dashboard.phase = 'paused';
    } else {
      const wasPaused = dashboard.phase === 'paused';
      dashboard.phase = next;
      dashboard.paused_from = null;
      if (next === 'quit') {
        dashboard.remaining = 0;
        dashboard.smoke_free_seconds = 0;
        dashboard.attempt_number = wasPaused ? 2 : 1;
        dashboard.next_milestone_seconds = 86400;
        dashboard.next_milestone_label = '1 день';
      }
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ phase: dashboard.phase, remaining: dashboard.remaining }) });
  });
  await page.route('**/api/v1/events', async route => {
    const payload = await route.request().postDataJSON();
    events.push(payload);
    if (payload.kind === 'smoked' && dashboard.phase === 'last_pack') {
      dashboard.remaining = Math.max(0, dashboard.remaining - 1);
      return route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify({ intervention: 'Счётчик обновлён без оценки.' }) });
    }
    dashboard.phase = 'quit';
    dashboard.smoke_free_seconds = 0;
    dashboard.best_smoke_free_seconds = 86400;
    dashboard.attempt_number = 3;
    dashboard.recovery_until = '2099-07-14T12:00:00Z';
    dashboard.recovery_steps = ['Сделать спокойный вдох', 'Выбрать следующий маленький шаг'];
    return route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify({ intervention: 'Начни с короткой паузы.' }) });
  });

  await page.goto('/app');
  await expect(page.getByRole('heading', { name: 'Осталось 7', level: 1 })).toBeVisible();
  await expect(page.getByRole('progressbar', { name: 'Остаток последней пачки' })).toHaveAttribute('aria-valuenow', '7');
  await page.getByRole('button', { name: /Отметить сигарету/ }).click();
  await expect(page.getByRole('heading', { name: 'Осталось 6', level: 1 })).toBeVisible();
  await expect(page.getByRole('progressbar', { name: 'Остаток последней пачки' })).toHaveAttribute('aria-valuenow', '6');
  expect(events[0]).toMatchObject({ kind: 'smoked', trigger: 'stress' });
  await page.getByRole('button', { name: /Я больше не курю/ }).click();
  await expect(page.getByRole('heading', { name: 'Твой путь продолжается', level: 1 })).toBeVisible();
  await expect(page.getByText('Попытка 1')).toBeVisible();

  const pauseOpener = page.getByRole('button', { name: 'Поставить путь на паузу' });
  await pauseOpener.click();
  const pauseDialog = page.getByRole('dialog', { name: 'Поставить путь на паузу?' });
  await expect(pauseDialog).toBeVisible();
  expect((await new AxeBuilder({ page }).include('.path-pause-dialog').analyze()).violations).toEqual([]);
  await pauseDialog.getByRole('button', { name: 'Остаться в пути' }).click();
  await expect(pauseOpener).toBeFocused();
  await pauseOpener.click();
  await pauseDialog.getByRole('button', { name: 'Поставить на паузу' }).click();
  await expect(page.getByRole('heading', { name: 'Можно продолжить без спешки', level: 1 })).toBeVisible();

  await page.getByRole('button', { name: /Продолжить путь/ }).click();
  await expect(page.getByText('Попытка 2')).toBeVisible();
  const relapseOpener = page.getByRole('button', { name: 'Отметить срыв без стыда' });
  await relapseOpener.click();
  const relapseDialog = page.getByRole('dialog', { name: 'Отметить сложный момент?' });
  await expect(relapseDialog).toContainText('лучший результат и вся история останутся');
  expect(events.filter(item => item.kind === 'relapse')).toHaveLength(0);
  expect((await new AxeBuilder({ page }).include('.path-relapse-dialog').analyze()).violations).toEqual([]);
  await relapseDialog.getByRole('button', { name: 'Вернуться без отметки' }).click();
  await expect(relapseOpener).toBeFocused();

  await relapseOpener.click();
  await relapseDialog.getByRole('button', { name: 'Сохранить и восстановиться' }).click();
  await expect(page.getByRole('heading', { name: 'Путь продолжается', level: 2 })).toBeVisible();
  await expect(page.getByText('Попытка 3')).toBeVisible();
  await expect(page.getByText('Лучший период').locator('..')).toContainText('1 д.');
  expect(transitions).toEqual([{ phase: 'quit' }, { phase: 'paused' }, { phase: 'quit' }]);
  expect(events).toHaveLength(2);
  expect(events[1]).toMatchObject({ kind: 'relapse' });
  expect((await new AxeBuilder({ page }).include('.path-app-shell').analyze()).violations).toEqual([]);
});
