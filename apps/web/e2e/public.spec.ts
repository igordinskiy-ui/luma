import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/launch-status', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ public_launch_enabled: true }) }));
});

test('public landing is accessible and has one primary entry action', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Следующий честный шаг');
  await expect(page.getByRole('link', { name: /Войти через Telegram/ })).toHaveCount(1);
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
  const undersizedFooterTargets = await page.evaluate(() => Array.from(document.querySelectorAll('.path-public-footer a'))
    .map(element => ({ text: element.textContent?.trim(), ...element.getBoundingClientRect().toJSON() }))
    .filter(rect => rect.width < 44 || rect.height < 44));
  expect(undersizedFooterTargets).toEqual([]);
});

test('production hides the development-only design route', async ({ page }) => {
  await page.goto('/?designs');
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Следующий честный шаг');
});

test('public landing never exposes login before launch status is verified and offers retry', async ({ page }) => {
  await page.unroute('**/api/v1/launch-status');
  let attempts = 0;
  await page.route('**/api/v1/launch-status', route => {
    attempts += 1;
    return attempts === 1
      ? route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ error: { code: 'dependency_unavailable', message: 'Later', request_id: 'launch-check-1' } }) })
      : route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ public_launch_enabled: true }) });
  });
  await page.goto('/');
  await expect(page.getByRole('link', { name: /Войти через Telegram/ })).toHaveCount(0);
  await expect(page.getByText('Не удалось проверить доступ.', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Проверить доступ' }).click();
  await expect(page.getByRole('link', { name: /Войти через Telegram/ })).toBeVisible();
});

test('public guides have unique metadata and no automated accessibility violations', async ({ page }) => {
  for (const path of ['/guide/craving', '/guide/coffee', '/guide/recovery']) {
    await page.goto(path);
    await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1);
    await expect(page.locator('meta[name="description"]')).toHaveAttribute('content', /.+/);
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations, path).toEqual([]);
  }
});

test('feedback login gate and pending legal states are explicit and accessible', async ({ page }) => {
  await page.goto('/feedback');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Расскажи');
  await expect(page.getByRole('button', { name: 'Войти через Telegram' })).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);

  for (const path of ['/consent.html', '/privacy.html', '/terms.html']) {
    await page.goto(path);
    await expect(page.locator('main[data-approval="pending"]')).toBeVisible();
    await expect(page.locator('meta[name="robots"]')).toHaveAttribute('content', 'noindex');
    expect(await page.locator('body').innerText()).not.toContain('['.repeat(2));
    expect((await new AxeBuilder({ page }).analyze()).violations, path).toEqual([]);
    await page.setViewportSize({ width: 320, height: 800 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(320);
  }
});

test('authenticated feedback submits a bounded category and clears the draft', async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.setItem('kurilka-access-token', 'feedback-e2e-token');
    sessionStorage.setItem('kurilka-user-id', '42');
  });
  let payload: Record<string, unknown> | null = null;
  await page.route('**/api/v1/feedback', async route => {
    payload = await route.request().postDataJSON();
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ feedback_id: 12, status: 'open' }) });
  });
  await page.goto('/feedback');
  await page.getByLabel('Тема').selectOption('bug');
  await page.getByRole('textbox', { name: 'Сообщение' }).fill('Кнопка повтора не сработала с первого раза.');
  await page.getByRole('button', { name: /Отправить/ }).click();
  await expect(page.getByRole('status')).toHaveText('Спасибо, сообщение отправлено.');
  await expect(page.getByRole('textbox', { name: 'Сообщение' })).toHaveValue('');
  expect(payload).toEqual({ category: 'bug', body: 'Кнопка повтора не сработала с первого раза.' });
});

test('installed PWA reloads its public shell while fully offline', async ({ page, context }) => {
  await page.goto('/');
  await page.evaluate(async () => { await navigator.serviceWorker.ready; });
  await page.reload();
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Следующий честный шаг');
  await context.setOffline(true);
  try {
    await page.reload();
    await expect(page.getByRole('heading', { level: 1 })).toContainText('Следующий честный шаг');
  } finally {
    await context.setOffline(false);
  }
});

test('legal navigation cannot replace the offline app shell cache', async ({ page, context }) => {
  await page.goto('/');
  await page.evaluate(async () => { await navigator.serviceWorker.ready; });
  await page.reload();
  await expect.poll(() => page.evaluate(() => Boolean(navigator.serviceWorker.controller))).toBe(true);
  await page.goto('/privacy.html');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Политика обработки');
  await context.setOffline(true);
  try {
    await page.goto('/app');
    await expect(page.getByRole('heading', { level: 1 })).toContainText('Следующий честный шаг');
    await page.goto('/privacy.html');
    await expect(page.getByRole('heading', { level: 1 })).toContainText('Политика обработки');
  } finally {
    await context.setOffline(false);
  }
});
