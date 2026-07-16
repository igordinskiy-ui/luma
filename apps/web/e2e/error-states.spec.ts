import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

const states = [
  { status: 401, heading: 'Не удалось войти', code: 'session_expired' },
  { status: 429, heading: 'Нужна короткая пауза', code: 'rate_limited' },
  { status: 503, heading: 'Сервис временно недоступен', code: 'dependency_unavailable' },
  { status: 500, heading: 'Не получилось открыть путь', code: 'internal_error' },
] as const;

for (const state of states) {
  test(`bootstrap ${state.status} has a recoverable accessible state`, async ({ page }) => {
    await page.addInitScript(() => {
      sessionStorage.setItem('kurilka-access-token', 'error-state-token');
      sessionStorage.setItem('kurilka-user-id', '42');
    });
    await page.route('**/api/v1/bootstrap', route => route.fulfill({ status: state.status, contentType: 'application/json', body: JSON.stringify({ error: { code: state.code, message: 'Safe public message', request_id: `request-${state.status}` } }) }));
    await page.goto('/app');
    await expect(page.getByRole('heading', { name: state.heading, level: 1 })).toBeVisible();
    await expect(page.getByText(`Код обращения: request-${state.status}`)).toBeVisible();
    if (state.status === 503) {
      await expect(page.getByRole('button', { name: 'Попробовать снова' })).toBeVisible();
      await expect(page.getByRole('link', { name: 'Сообщить о проблеме' })).toBeVisible();
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  });
}

test('closed public launch is explained without pretending that the service failed', async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.setItem('kurilka-access-token', 'launch-gate-token');
    sessionStorage.setItem('kurilka-user-id', '42');
  });
  await page.route('**/api/v1/bootstrap', route => route.fulfill({
    status: 503,
    contentType: 'application/json',
    body: JSON.stringify({ error: { code: 'public_launch_disabled', message: 'Public launch is not enabled', request_id: 'request-launch' } }),
  }));
  await page.goto('/app');
  await expect(page.getByRole('heading', { name: 'Готовим запуск', level: 1 })).toBeVisible();
  await expect(page.getByRole('link', { name: 'На главную' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Попробовать снова' })).toHaveCount(0);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test('network loss shows an offline state without asking to re-enter data', async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.setItem('kurilka-access-token', 'offline-state-token');
    sessionStorage.setItem('kurilka-user-id', '42');
  });
  await page.route('**/api/v1/bootstrap', route => route.abort('internetdisconnected'));
  await page.goto('/app');
  await expect(page.getByRole('heading', { name: 'Сейчас нет сети', level: 1 })).toBeVisible();
  await expect(page.getByText('останутся на устройстве', { exact: false })).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test('slow bootstrap keeps an announced loading state until data arrives', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.addInitScript(() => {
    sessionStorage.setItem('kurilka-access-token', 'slow-state-token');
    sessionStorage.setItem('kurilka-user-id', '42');
  });
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  await page.route('**/api/v1/bootstrap', async route => {
    await gate;
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ age_confirmed: false, consent_current: false, onboarded: false }) });
  });
  await page.goto('/app');
  await expect(page.getByRole('status')).toContainText('Открываем твой путь');
  await expect(page.locator('.path-loader')).toHaveCSS('animation-name', 'none');
  await expect(page.locator('html')).toHaveCSS('scroll-behavior', 'auto');
  release();
  await expect(page.getByRole('heading', { name: 'Где начинается твой путь?', level: 1 })).toBeVisible();
});
