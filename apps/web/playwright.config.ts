import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  snapshotPathTemplate: '{testDir}/__screenshots__/{testFilePath}/{arg}-{projectName}-{platform}{ext}',
  fullyParallel: true,
  workers: 4,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://127.0.0.1:41792',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  expect: {
    toHaveScreenshot: {
      animations: 'disabled',
      caret: 'hide',
      scale: 'css',
      threshold: 0.3,
      maxDiffPixelRatio: 0.03,
    },
  },
  projects: [
    { name: 'mobile-390', grepInvert: /@zoom/, use: { ...devices['Pixel 7'], viewport: { width: 390, height: 844 } } },
    { name: 'mobile-430', grepInvert: /@zoom/, use: { ...devices['Pixel 7'], viewport: { width: 430, height: 932 } } },
    { name: 'tablet-768', grepInvert: /@zoom/, use: { ...devices['Desktop Chrome'], viewport: { width: 768, height: 1024 } } },
    { name: 'desktop-1440', grepInvert: /@zoom/, use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } },
    { name: 'zoom-200-reflow', grep: /@zoom/, use: { ...devices['Desktop Chrome'], viewport: { width: 320, height: 512 } } },
  ],
});
