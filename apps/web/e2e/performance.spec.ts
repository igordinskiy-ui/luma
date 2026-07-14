import { expect, test } from '@playwright/test';

test('public landing stays inside local web-vitals guardrails', async ({ page }) => {
  await page.addInitScript(() => {
    const target = window as typeof window & { __pathVitals?: { cls: number; lcp: number; inp: number } };
    target.__pathVitals = { cls: 0, lcp: 0, inp: 0 };
    new PerformanceObserver(list => {
      for (const entry of list.getEntries() as Array<PerformanceEntry & { hadRecentInput?: boolean; value?: number }>) {
        if (!entry.hadRecentInput) target.__pathVitals!.cls += entry.value || 0;
      }
    }).observe({ type: 'layout-shift', buffered: true });
    new PerformanceObserver(list => {
      const entries = list.getEntries();
      if (entries.length) target.__pathVitals!.lcp = entries[entries.length - 1].startTime;
    }).observe({ type: 'largest-contentful-paint', buffered: true });
    new PerformanceObserver(list => {
      for (const entry of list.getEntries() as Array<PerformanceEntry & { duration: number; interactionId?: number }>) {
        if (entry.interactionId) target.__pathVitals!.inp = Math.max(target.__pathVitals!.inp, entry.duration);
      }
    }).observe({ type: 'event', buffered: true, durationThreshold: 16 } as PerformanceObserverInit);
  });

  await page.goto('/');
  await page.getByRole('link', { name: 'Как это работает' }).click();
  await expect(page).toHaveURL(/#how$/);
  await page.waitForTimeout(100);
  const metrics = await page.evaluate(() => {
    const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
    const vitals = (window as typeof window & { __pathVitals: { cls: number; lcp: number; inp: number } }).__pathVitals;
    return { ...vitals, responseEnd: navigation.responseEnd };
  });

  expect(metrics.responseEnd).toBeLessThan(2500);
  expect(metrics.lcp).toBeGreaterThan(0);
  expect(metrics.lcp).toBeLessThan(2500);
  expect(metrics.cls).toBeLessThan(0.1);
  expect(metrics.inp).toBeLessThan(200);
});
