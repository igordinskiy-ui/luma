import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api, authenticateDevelopment, consumeOidcCompletion, OidcCompletionError, safeOidcReturnPath } from '../api';

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
  history.replaceState(null, '', '/app');
  vi.restoreAllMocks();
});

describe('OIDC interrupted-flow return path', () => {
  it('allows only known same-origin product routes', () => {
    expect(safeOidcReturnPath('/journal')).toBe('/journal');
    expect(safeOidcReturnPath('/app/support')).toBe('/app/support');
    expect(safeOidcReturnPath('/staff')).toBe('/staff');
    expect(safeOidcReturnPath('//evil.example/path')).toBe('/app');
    expect(safeOidcReturnPath('https://evil.example')).toBe('/app');
    expect(safeOidcReturnPath('/unknown')).toBe('/app');
  });
});

describe('OIDC completion recovery', () => {
  it('retries a pending one-time exchange after a network interruption and restores the route', async () => {
    sessionStorage.setItem('kurilka-oidc-state', 'client-state-1234567890123456');
    sessionStorage.setItem('kurilka-oidc-return', '/journal');
    history.replaceState(null, '', '/app#oidc_code=completion-code-1234567890123456&state=client-state-1234567890123456');
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockRejectedValueOnce(new TypeError('network'))
      .mockResolvedValueOnce(new Response(JSON.stringify({ access_token: 'signed-session', token_type: 'bearer', user_id: 42 }), { status: 200, headers: { 'Content-Type': 'application/json' } }));

    await expect(consumeOidcCompletion()).rejects.toMatchObject({ reason: 'temporary', retryable: true } satisfies Partial<OidcCompletionError>);
    expect(location.hash).toBe('');
    expect(sessionStorage.getItem('kurilka-oidc-pending')).not.toBeNull();

    await expect(consumeOidcCompletion()).resolves.toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(location.pathname).toBe('/journal');
    expect(sessionStorage.getItem('kurilka-access-token')).toBe('signed-session');
    expect(sessionStorage.getItem('kurilka-oidc-pending')).toBeNull();
  });

  it('discards an expired pending exchange without touching product drafts', async () => {
    sessionStorage.setItem('kurilka-oidc-state', 'client-state-1234567890123456');
    sessionStorage.setItem('kurilka-oidc-return', '/settings');
    sessionStorage.setItem('kurilka-oidc-pending', JSON.stringify({ code: 'completion-code-1234567890123456', state: 'client-state-1234567890123456', createdAt: Date.now() - 91_000 }));
    localStorage.setItem('kurilka-onboarding-draft-v2', '{"step":2}');

    await expect(consumeOidcCompletion()).rejects.toMatchObject({ reason: 'expired', retryable: false } satisfies Partial<OidcCompletionError>);
    expect(sessionStorage.getItem('kurilka-oidc-pending')).toBeNull();
    expect(localStorage.getItem('kurilka-onboarding-draft-v2')).toBe('{"step":2}');
  });
});

describe('bearer replacement race', () => {
  it('does not let a late 401 from an old request erase a newer session', async () => {
    sessionStorage.setItem('kurilka-access-token', 'old-session');
    sessionStorage.setItem('kurilka-user-id', '41');
    let finishOldRequest: (response: Response) => void = () => undefined;
    const oldResponse = new Promise<Response>(resolve => { finishOldRequest = resolve; });
    vi.spyOn(globalThis, 'fetch')
      .mockReturnValueOnce(oldResponse)
      .mockResolvedValueOnce(new Response(JSON.stringify({ access_token: 'new-session', token_type: 'bearer', user_id: 42 }), { status: 200, headers: { 'Content-Type': 'application/json' } }));

    const staleTelemetry = api.clientTelemetry('session_started', '33333333-3333-4333-8333-333333333333');
    await authenticateDevelopment();
    finishOldRequest(new Response(JSON.stringify({ error: { code: 'invalid_session', message: 'Expired', request_id: 'late-401' } }), { status: 401, headers: { 'Content-Type': 'application/json' } }));

    await expect(staleTelemetry).rejects.toMatchObject({ status: 401 });
    expect(sessionStorage.getItem('kurilka-access-token')).toBe('new-session');
    expect(sessionStorage.getItem('kurilka-user-id')).toBe('42');
  });
});
