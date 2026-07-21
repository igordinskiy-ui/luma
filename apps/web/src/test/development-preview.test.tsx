import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  bootstrap: vi.fn(),
  dashboard: vi.fn(),
  clientTelemetry: vi.fn(),
  authenticateDevelopment: vi.fn(),
  syncQueued: vi.fn(),
}));

vi.mock('../api', () => {
  class ApiError extends Error {
    constructor(public status: number, message: string, public code = `http_${status}`, public requestId?: string) { super(message); }
  }
  return {
    ApiError,
    api: { bootstrap: mocks.bootstrap, dashboard: mocks.dashboard, clientTelemetry: mocks.clientTelemetry },
    authenticate: vi.fn(),
    authenticateDevelopment: mocks.authenticateDevelopment,
    authToken: () => 'stale-preview-token',
    beginOidcLogin: vi.fn(),
    consumeOidcCompletion: vi.fn().mockResolvedValue(false),
    currentUserId: () => '42',
    OidcCompletionError: class extends Error {},
  };
});
vi.mock('../offline', () => ({ syncQueued: mocks.syncQueued }));
vi.mock('../telegram', () => ({ initialiseTelegram: () => null }));
vi.mock('../features/journey/DashboardView', () => ({ DashboardView: () => <h1>Продолжаем путь</h1> }));
vi.mock('../features/onboarding/Onboarding', () => ({ ConsentRenewal: () => null, Onboarding: () => null }));
vi.mock('../features/public/PublicPages', () => ({ Landing: () => null }));

import { ApiError } from '../api';
import { App } from '../features/app/App';

describe('isolated development preview session recovery', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.syncQueued.mockResolvedValue(undefined);
    mocks.authenticateDevelopment.mockResolvedValue(undefined);
    mocks.clientTelemetry.mockResolvedValue(undefined);
    mocks.dashboard.mockResolvedValue({});
  });

  it('renews a stale preview token before any product request and returns to the saved screen', async () => {
    vi.stubEnv('VITE_TEST_PREVIEW', 'true');
    mocks.bootstrap.mockResolvedValueOnce({ age_confirmed: true, consent_current: true, onboarded: true });

    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Продолжаем путь' })).toBeVisible();
    expect(mocks.authenticateDevelopment).toHaveBeenCalledOnce();
    expect(mocks.bootstrap).toHaveBeenCalledOnce();
    expect(mocks.authenticateDevelopment.mock.invocationCallOrder[0]).toBeLessThan(mocks.bootstrap.mock.invocationCallOrder[0]);
  });

  it('keeps the normal re-login UI when the explicit preview flag is absent', async () => {
    vi.stubEnv('VITE_TEST_PREVIEW', 'false');
    mocks.bootstrap.mockRejectedValueOnce(new ApiError(401, 'Expired', 'invalid_session', 'preview-auth-401'));

    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Нужно войти снова' })).toBeVisible();
    expect(screen.getByText('Код обращения:')).toHaveTextContent('preview-auth-401');
    expect(mocks.authenticateDevelopment).not.toHaveBeenCalled();
  });
});
